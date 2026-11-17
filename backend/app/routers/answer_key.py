from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.answer_key import apply_answer_key, parse_key_file, replace_key
from app.database import SyncSessionLocal, get_session
from app.models import AnswerKeyRow
from app.routers.documents import require_uploads
from app.schemas import AnswerKeyStats

router = APIRouter(prefix="/api/answer-key", tags=["answer-key"])

MAX_KEY_BYTES = 5 * 1024 * 1024


@router.get("")
async def answer_key_summary(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await session.scalar(select(func.count(AnswerKeyRow.id))) or 0
    return {"rows": rows}


def _load_and_apply(data: bytes, filename: str) -> dict:
    rows = parse_key_file(data, filename)
    if not rows:
        raise ValueError("El archivo no contiene filas válidas (materia, pagina, ejercicio, respuesta)")
    with SyncSessionLocal() as s:
        replace_key(s, rows)
        stats = apply_answer_key(s)
        s.commit()
    return stats


@router.post("", response_model=AnswerKeyStats, dependencies=[Depends(require_uploads)])
async def upload_answer_key(file: UploadFile = File(...)) -> AnswerKeyStats:
    """Reemplaza la clave con un JSON/CSV y la aplica a todas las preguntas ya extraídas."""
    data = await file.read(MAX_KEY_BYTES + 1)
    if len(data) > MAX_KEY_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La clave supera los 5 MB")
    try:
        stats = await run_in_threadpool(_load_and_apply, data, file.filename or "")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Clave inválida: {exc}") from exc
    return AnswerKeyStats(**stats)
