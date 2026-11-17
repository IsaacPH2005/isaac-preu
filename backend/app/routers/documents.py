import logging
import re
import shutil
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import Document, Question
from app.schemas import DocumentOut
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

PROCESS_TASK = "bancopreu.process_document"
CHUNK = 1024 * 1024


def require_uploads() -> None:
    """En producción (ALLOW_UPLOADS=false) el banco es de solo lectura."""
    if not settings.allow_uploads:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La gestión de documentos está deshabilitada")


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return (stem or "documento")[:80]


def _save_upload(upload: UploadFile, dest: Path) -> int:
    """Guarda el archivo en disco por bloques; devuelve bytes escritos."""
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    upload.file.seek(0)
    with dest.open("wb") as out:
        while chunk := upload.file.read(CHUNK):
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"El archivo supera el límite de {settings.max_upload_mb} MB",
                )
            out.write(chunk)
    return written


def _count_pages(path: Path) -> int:
    with fitz.open(path) as pdf:
        if not pdf.is_pdf:
            raise ValueError("no es un PDF")
        return pdf.page_count


async def _with_counts(session: AsyncSession, docs: list[Document]) -> list[DocumentOut]:
    if not docs:
        return []
    rows = await session.execute(
        select(Question.document_id, func.count(Question.id))
        .where(Question.document_id.in_([d.id for d in docs]))
        .group_by(Question.document_id)
    )
    counts = dict(rows.all())
    out = []
    for d in docs:
        item = DocumentOut.model_validate(d)
        item.question_count = counts.get(d.id, 0)
        out.append(item)
    return out


async def _get_doc(session: AsyncSession, document_id: int) -> Document:
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return doc


@router.post(
    "/upload",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_uploads)],
)
async def upload_document(
    file: UploadFile = File(...), session: AsyncSession = Depends(get_session)
) -> DocumentOut:
    original = file.filename or "documento.pdf"
    if not original.lower().endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo se aceptan archivos PDF")

    settings.pdf_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:12]}_{_safe_stem(original)}.pdf"
    dest = settings.pdf_dir / stored_name

    try:
        await run_in_threadpool(_save_upload, file, dest)
        total_pages = await run_in_threadpool(_count_pages, dest)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except Exception as exc:  # PDF corrupto o ilegible
        dest.unlink(missing_ok=True)
        logger.warning("PDF inválido %s: %s", original, exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo no es un PDF válido") from exc
    finally:
        await file.close()

    if total_pages == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El PDF no tiene páginas")

    doc = Document(
        filename=original,
        file_path=f"pdfs/{stored_name}",
        total_pages=total_pages,
        processed_pages=0,
        status="pending",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    celery_app.send_task(PROCESS_TASK, args=[doc.id])
    logger.info("Documento %s encolado (%s páginas)", doc.id, total_pages)
    return DocumentOut.model_validate(doc)


@router.get("", response_model=list[DocumentOut])
async def list_documents(session: AsyncSession = Depends(get_session)) -> list[DocumentOut]:
    docs = (await session.scalars(select(Document).order_by(Document.created_at.desc()))).all()
    return await _with_counts(session, list(docs))


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: int, session: AsyncSession = Depends(get_session)) -> DocumentOut:
    doc = await _get_doc(session, document_id)
    return (await _with_counts(session, [doc]))[0]


@router.post("/{document_id}/reprocess", response_model=DocumentOut, dependencies=[Depends(require_uploads)])
async def reprocess_document(
    document_id: int,
    resume: bool = False,
    session: AsyncSession = Depends(get_session),
) -> DocumentOut:
    """resume=true continúa desde la última página guardada; si no, empieza de cero."""
    doc = await _get_doc(session, document_id)
    if doc.status in ("pending", "processing"):
        raise HTTPException(status.HTTP_409_CONFLICT, "El documento ya se está procesando")
    resume = resume and 0 < doc.processed_pages < doc.total_pages
    doc.status = "pending"
    if not resume:
        doc.processed_pages = 0
    doc.error_message = None
    await session.commit()
    await session.refresh(doc)
    celery_app.send_task(PROCESS_TASK, args=[doc.id], kwargs={"resume": resume})
    return (await _with_counts(session, [doc]))[0]


@router.delete(
    "/{document_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_uploads)]
)
async def delete_document(document_id: int, session: AsyncSession = Depends(get_session)) -> None:
    doc = await _get_doc(session, document_id)
    pdf_path = settings.storage_path / doc.file_path
    pages_path = settings.pages_dir / str(doc.id)
    await session.delete(doc)
    await session.commit()
    pdf_path.unlink(missing_ok=True)
    shutil.rmtree(pages_path, ignore_errors=True)
