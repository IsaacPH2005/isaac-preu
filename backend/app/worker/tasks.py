"""Pipeline de ingesta: PDF -> PNG por página -> Gemini Vision -> preguntas en BD."""

import logging
import re
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

from sqlalchemy import delete, distinct, select, update
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SyncSessionLocal
from app.models import Document, Question
from app.subjects import UNCLASSIFIED, clean_topic, normalize_subject, repair_latex
from app.worker.celery_app import celery_app
from app.worker.gemini import PageExtraction, ProviderNotConfigured, fatal_error_message
from app.worker.llm import AllProvidersExhausted, ExtractionClient
from app.worker.pdf_render import RenderedPage, render_pdf_pages

logger = logging.getLogger(__name__)


class DocumentDeleted(Exception):
    """El documento fue eliminado mientras se procesaba."""


class GeminiFatalError(RuntimeError):
    """Error permanente de Gemini (modelo inexistente, clave inválida…): no sigue con más páginas."""


@dataclass
class IngestState:
    current_subject: str | None = None
    last_question_id: int | None = None
    failed_pages: list[int] = field(default_factory=list)
    question_count: int = 0


def _set_status(document_id: int, **values) -> None:
    with SyncSessionLocal() as s:
        s.execute(update(Document).where(Document.id == document_id).values(**values))
        s.commit()


def _extract(client: ExtractionClient, page: RenderedPage) -> PageExtraction | None:
    """Se ejecuta en un hilo. Devuelve None si la página falla tras los reintentos."""
    try:
        return client.extract_page(page.abs_path.read_bytes(), page.number)
    except AllProvidersExhausted as exc:
        raise GeminiFatalError(str(exc)) from exc
    except Exception as exc:
        fatal = fatal_error_message(exc)
        if fatal:
            raise GeminiFatalError(fatal) from exc
        logger.exception("Fallo al extraer la página %s", page.number)
        return None


def _clean_options(options: list[str]) -> list[str]:
    return [repair_latex(o) for o in options if o and o.strip()]


_MATH_RE = re.compile(r"\$\$.*?\$\$|\$.*?\$|\\\(.*?\\\)", re.S)


def _plain_text(statement: str | None) -> str:
    return _MATH_RE.sub("", statement or "").strip(" .:-\n")


def _looks_like_fragment(eq) -> bool:
    """Entrada sin número ni materia y casi sin texto: restos de la pregunta anterior."""
    if eq.number or (eq.subject or "").strip():
        return False
    return len(_plain_text(eq.statement)) < 25


def _persist_page(document_id: int, page: RenderedPage, result: PageExtraction | None, state: IngestState) -> None:
    with SyncSessionLocal() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            raise DocumentDeleted()

        if result is None:
            state.failed_pages.append(page.number)
        else:
            questions = list(result.questions)
            cont_text = repair_latex(result.continuation_text)
            cont_opts = _clean_options(result.continuation_options)
            # Red de seguridad: alternativas sueltas al inicio de página tomadas como pregunta nueva
            if questions and not cont_text and not cont_opts and _looks_like_fragment(questions[0]):
                frag = questions.pop(0)
                cont_opts = _clean_options(frag.options)
                if not cont_opts or _plain_text(frag.statement):
                    cont_text = repair_latex(frag.statement)

            # 1) Continuación de la última pregunta de la página anterior
            if (cont_text or cont_opts) and state.last_question_id:
                prev = s.get(Question, state.last_question_id)
                if prev is not None:
                    if cont_text:
                        prev.statement = f"{prev.statement}\n{cont_text}".strip()
                    if cont_opts:
                        prev.options = [*(prev.options or []), *cont_opts]
                    prev.has_diagram = prev.has_diagram or result.continuation_has_diagram

            # 2) Preguntas nuevas (heredando la materia si no hay encabezado visible)
            new_questions: list[Question] = []
            for eq in questions:
                statement = repair_latex(eq.statement)
                options = _clean_options(eq.options)
                if not statement and not options:
                    continue
                subject = normalize_subject(eq.subject) or state.current_subject or UNCLASSIFIED
                state.current_subject = subject
                q = Question(
                    document_id=document_id,
                    question_number=max(0, eq.number or 0),
                    page_number=page.number,
                    page_image_path=page.rel_path,
                    subject=subject,
                    topic=clean_topic(eq.topic),
                    statement=statement,
                    options=options,
                    has_diagram=bool(eq.has_diagram),
                )
                s.add(q)
                new_questions.append(q)

            s.flush()
            if new_questions:
                state.last_question_id = new_questions[-1].id
                state.question_count += len(new_questions)

        doc.processed_pages = page.number
        try:
            s.commit()
        except IntegrityError as exc:  # FK rota: documento borrado a mitad
            s.rollback()
            raise DocumentDeleted() from exc


def normalize_topics(document_id: int, client: ExtractionClient) -> None:
    """Agrupa temas equivalentes ('División de polinomios' ~ 'División algebraica de polinomios')."""
    with SyncSessionLocal() as s:
        subjects = s.scalars(
            select(distinct(Question.subject)).where(Question.document_id == document_id)
        ).all()

    for subject in subjects:
        with SyncSessionLocal() as s:
            doc_topics = sorted(
                s.scalars(
                    select(distinct(Question.topic)).where(
                        Question.document_id == document_id, Question.subject == subject
                    )
                ).all()
            )
            existing = sorted(
                s.scalars(
                    select(distinct(Question.topic)).where(
                        Question.document_id != document_id, Question.subject == subject
                    )
                ).all()
            )
        if len(doc_topics) < 2 and not existing:
            continue

        try:
            mapping = client.group_topics(subject, doc_topics, existing[:400])
        except Exception:
            logger.exception("No se pudieron normalizar los temas de %s", subject)
            continue

        changes = {orig: clean_topic(canon) for orig, canon in mapping.items() if clean_topic(canon) != orig}
        if not changes:
            continue
        with SyncSessionLocal() as s:
            for orig, canon in changes.items():
                s.execute(
                    update(Question)
                    .where(
                        Question.document_id == document_id,
                        Question.subject == subject,
                        Question.topic == orig,
                    )
                    .values(topic=canon)
                )
            s.commit()
        logger.info("Doc %s / %s: %d temas fusionados", document_id, subject, len(changes))


@celery_app.task(name="bancopreu.process_document", bind=True, acks_late=True)
def process_document(self, document_id: int, resume: bool = False) -> dict:
    """
    resume=False: procesa desde cero (borra preguntas previas).
    resume=True: continúa tras la última página guardada (p. ej. tras agotar la cuota diaria).
    """
    state = IngestState()
    with SyncSessionLocal() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            logger.warning("Documento %s no existe", document_id)
            return {"status": "missing"}
        pdf_path = settings.storage_path / doc.file_path
        start = doc.processed_pages if resume else 0
        # Idempotente: elimina lo que se va a (re)generar.
        s.execute(
            delete(Question).where(Question.document_id == document_id, Question.page_number > start)
        )
        if start:
            last = s.scalars(
                select(Question)
                .where(Question.document_id == document_id)
                .order_by(Question.page_number.desc(), Question.id.desc())
                .limit(1)
            ).first()
            if last is not None:
                state.current_subject = last.subject
                state.last_question_id = last.id
        doc.status = "processing"
        doc.processed_pages = start
        doc.error_message = None
        s.commit()

    try:
        client = ExtractionClient()
        pages = render_pdf_pages(pdf_path, document_id)
        _set_status(document_id, total_pages=len(pages))
        logger.info("Doc %s: %d páginas renderizadas", document_id, len(pages))

        # Las llamadas a Gemini van en paralelo, pero se persisten en orden de página
        # para que la herencia de materia y las continuaciones sean correctas.
        todo = pages[start:]
        if start:
            logger.info("Doc %s: reanudando desde la página %d", document_id, start + 1)
        with ThreadPoolExecutor(max_workers=max(1, settings.gemini_concurrency)) as pool:
            futures: list[Future] = [pool.submit(_extract, client, p) for p in todo]
            try:
                for page, fut in zip(todo, futures):
                    _persist_page(document_id, page, fut.result(), state)
            except BaseException:
                for f in futures:
                    f.cancel()
                raise

        normalize_topics(document_id, client)

        if todo and len(state.failed_pages) == len(todo):
            raise RuntimeError("Gemini no pudo procesar ninguna página")

        message = None
        if state.failed_pages:
            shown = ", ".join(map(str, state.failed_pages[:20]))
            message = f"{len(state.failed_pages)} página(s) no se pudieron procesar: {shown}"
        _set_status(document_id, status="completed", processed_pages=len(pages), error_message=message)
        logger.info("Doc %s completado: %d preguntas", document_id, state.question_count)
        return {"status": "completed", "questions": state.question_count, "failed_pages": state.failed_pages}

    except DocumentDeleted:
        logger.info("Doc %s eliminado durante el procesamiento; se detiene", document_id)
        return {"status": "deleted"}
    except (ProviderNotConfigured, GeminiFatalError) as exc:
        logger.error("Doc %s abortado: %s", document_id, exc)
        _set_status(document_id, status="failed", error_message=str(exc))
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:
        logger.exception("Error procesando documento %s", document_id)
        _set_status(document_id, status="failed", error_message=f"{type(exc).__name__}: {exc}"[:2000])
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="bancopreu.normalize_topics", bind=True)
def normalize_topics_task(self, document_id: int) -> dict:
    """Vuelve a agrupar los temas de un documento sin volver a extraer sus páginas."""
    normalize_topics(document_id, ExtractionClient())
    return {"status": "ok"}
