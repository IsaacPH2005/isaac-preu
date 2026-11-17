"""Pipeline de ingesta: PDF -> PNG por página -> Gemini Vision -> preguntas en BD."""

import logging
import re
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

from sqlalchemy import delete, distinct, select, update
from sqlalchemy.exc import IntegrityError

from app.answer_key import apply_answer_key
from app.config import settings
from app.database import SyncSessionLocal
from app.exams import ExamInfo, parse_exam
from app.figures import extract_figures
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
    current_exam: ExamInfo | None = None
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


_LABEL_RE = re.compile(r"^\s*([A-Za-z]{0,3})\s*-?\s*(\d{1,3})\s*[.)\-:]*\s*$")


def _label_and_number(raw_label: str | None, raw_number: int | None) -> tuple[str, int]:
    """'G3' -> ('G3', 3); 'Q-13.-' -> ('Q-13', 13). El número impreso manda sobre el del modelo."""
    m = _LABEL_RE.match(raw_label or "")
    if m:
        prefix, num = m.group(1).upper(), int(m.group(2))
        sep = "-" if "-" in (raw_label or "").split(m.group(2))[0] else ""
        return f"{prefix}{sep}{num}"[:16], num
    number = max(0, raw_number or 0)
    return (str(number) if number else ""), number


def _looks_like_fragment(eq) -> bool:
    """Entrada sin número ni materia y casi sin texto: restos de la pregunta anterior."""
    if eq.number or (eq.label or "").strip() or (eq.subject or "").strip():
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
                exam = parse_exam(eq.exam_header) or state.current_exam
                state.current_exam = exam
                label, number = _label_and_number(eq.label, eq.number)
                q = Question(
                    document_id=document_id,
                    question_number=number,
                    question_label=label,
                    page_number=page.number,
                    page_image_path=page.rel_path,
                    subject=subject,
                    topic=clean_topic(eq.topic),
                    statement=statement,
                    options=options,
                    has_diagram=bool(eq.has_diagram),
                    figure_box=list(eq.figure_box or [])[:4] or None,
                    exam=exam.label if exam else "",
                    exam_type=exam.type if exam else "",
                    exam_year=exam.year if exam else None,
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
                if last.exam:
                    state.current_exam = ExamInfo(last.exam, last.exam_type, last.exam_year)
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
        # Figuras recortadas del PDF (imágenes incrustadas o caja indicada por la IA)
        try:
            with SyncSessionLocal() as s:
                fig_stats = extract_figures(s, document_id)
                s.commit()
            logger.info("Doc %s: figuras %s", document_id, fig_stats)
        except Exception:
            logger.exception("No se pudieron recortar las figuras del documento %s", document_id)
        # La clave oficial corrige materia/tema y añade respuesta y dificultad
        try:
            with SyncSessionLocal() as s:
                stats = apply_answer_key(s, document_id)
                s.commit()
            logger.info("Doc %s: clave aplicada %s", document_id, stats)
        except Exception:
            logger.exception("No se pudo aplicar la clave al documento %s", document_id)

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


def _page_for_solver(pdf_path, page_number: int, fallback) -> bytes:
    """Página en mayor resolución que la de la web (las figuras pequeñas se leen mejor)."""
    import fitz

    try:
        if pdf_path is not None and pdf_path.is_file():
            with fitz.open(pdf_path) as pdf:
                return pdf[page_number - 1].get_pixmap(dpi=220, alpha=False).tobytes("png")
    except Exception:
        logger.warning("No se pudo renderizar la página %s en alta resolución", page_number)
    return fallback.read_bytes() if fallback.is_file() else b""


@celery_app.task(name="bancopreu.solve_question", bind=True, acks_late=True)
def solve_question_task(self, question_id: int) -> dict:
    """Genera (o regenera) la solución con estrategia y tips de una pregunta."""
    from app.models import QuestionSolution
    from app.worker.solver import solve_payload

    with SyncSessionLocal() as s:
        q = s.get(Question, question_id)
        if q is None:
            return {"status": "missing"}
        prompt = solve_payload(q)
        figure_paths = [settings.storage_path / p for p in (q.figures or [])]
        page_path = settings.storage_path / q.page_image_path
        needs_vision = bool(q.has_diagram or q.figures)
        doc = s.get(Document, q.document_id)
        pdf_path = settings.storage_path / doc.file_path if doc else None
        page_number = q.page_number

    try:
        images = [p.read_bytes() for p in figure_paths if p.is_file()]
        images.append(_page_for_solver(pdf_path, page_number, page_path))
        result = ExtractionClient().solve_question([i for i in images if i], prompt, needs_vision=needs_vision)
        values = dict(
            status="done",
            figure_data=[x.strip() for x in result.figure_data if x and x.strip()],
            strategy=repair_latex(result.strategy),
            steps=[repair_latex(x) for x in result.steps if x and x.strip()],
            shortcut=repair_latex(result.shortcut),
            common_mistake=repair_latex(result.common_mistake),
            final_answer=(result.final_answer or "").strip().upper()[:8],
            reaches_key=result.reaches_key,
            confidence=result.confidence,
            note=result.note.strip(),
            error="",
        )
    except Exception as exc:
        logger.exception("No se pudo resolver la pregunta %s", question_id)
        values = dict(status="failed", error=(fatal_error_message(exc) or f"{type(exc).__name__}: {exc}")[:500])

    with SyncSessionLocal() as s:
        sol = s.get(QuestionSolution, question_id)
        if sol is None:
            if s.get(Question, question_id) is None:
                return {"status": "missing"}
            sol = QuestionSolution(question_id=question_id)
            s.add(sol)
        for k, v in values.items():
            setattr(sol, k, v)
        s.commit()
    return {"status": values["status"]}


@celery_app.task(name="bancopreu.extract_figures", bind=True)
def extract_figures_task(self, document_id: int) -> dict:
    """Vuelve a recortar las figuras de un documento sin volver a extraer sus páginas."""
    with SyncSessionLocal() as s:
        stats = extract_figures(s, document_id)
        s.commit()
    return stats
