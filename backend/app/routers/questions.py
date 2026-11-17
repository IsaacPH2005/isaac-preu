import math
import re
from dataclasses import asdict, dataclass

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ColumnElement, Select, and_, exists, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Document, Question, QuestionSolution
from app.schemas import (
    DifficultyCount,
    ExamCount,
    ExamTypeCount,
    FiltersOut,
    QuestionOut,
    QuestionPage,
    SubjectCount,
    TopicCount,
)
from app.subjects import strip_accents

router = APIRouter(prefix="/api", tags=["questions"])

_TOKEN_RE = re.compile(r"[a-z0-9ñ]+", re.I)


def build_tsquery(q: str) -> ColumnElement | None:
    """
    - Con comillas o operadores ("plano inclinado", -energia, or) -> websearch_to_tsquery.
    - Sin ellos -> búsqueda por prefijo de cada palabra (ideal para búsqueda instantánea:
      "ruff" encuentra "Ruffini").
    Siempre sin tildes (el índice también se construye sin tildes).
    """
    q = q.strip()
    if not q:
        return None
    if '"' in q or re.search(r"(^|\s)-\w|\bor\b", q, re.I):
        return func.websearch_to_tsquery("spanish", func.f_unaccent(q))
    tokens = _TOKEN_RE.findall(strip_accents(q).lower())
    if not tokens:
        return None
    expr = " & ".join(f"{t}:*" for t in tokens[:12])
    return func.to_tsquery("spanish", expr)


@dataclass
class QFilters:
    subject: str | None = None
    topic: str | None = None
    document_id: int | None = None
    has_diagram: bool | None = None
    exam: str | None = None
    exam_type: str | None = None
    page_from: int | None = None
    page_to: int | None = None
    difficulty: int | None = None
    has_answer: bool | None = None

    def without(self, *names: str) -> "QFilters":
        return QFilters(**{k: (None if k in names else v) for k, v in asdict(self).items()})


def _apply_filters(stmt: Select, f: QFilters) -> Select:
    conds = []
    if f.subject:
        conds.append(Question.subject == f.subject)
    if f.topic:
        conds.append(Question.topic == f.topic)
    if f.document_id:
        conds.append(Question.document_id == f.document_id)
    if f.has_diagram:
        conds.append(Question.has_diagram.is_(True))
    if f.exam:
        conds.append(Question.exam == f.exam)
    if f.exam_type:
        conds.append(Question.exam_type == f.exam_type)
    if f.page_from:
        conds.append(Question.page_number >= f.page_from)
    if f.page_to:
        conds.append(Question.page_number <= f.page_to)
    if f.difficulty:
        conds.append(Question.difficulty == f.difficulty)
    if f.has_answer:
        conds.append(Question.answer != "")
    return stmt.where(and_(*conds)) if conds else stmt


def _filters_dep(
    subject: str | None = Query(None, description="Materia, ej. FISICA"),
    topic: str | None = Query(None, description="Tema exacto"),
    document_id: int | None = Query(None),
    has_diagram: bool | None = Query(None, description="Solo preguntas con gráficos"),
    exam: str | None = Query(None, description="Examen exacto, ej. 'Segundo examen de ingreso 1-2012'"),
    exam_type: str | None = Query(None, description="Tipo: 'Primera opción', '1er parcial Pre-U'…"),
    page_from: int | None = Query(None, ge=1, description="Página del libro desde"),
    page_to: int | None = Query(None, ge=1, description="Página del libro hasta"),
    difficulty: int | None = Query(None, ge=1, le=4, description="1 fácil … 4 experto"),
    has_answer: bool | None = Query(None, description="Solo preguntas con respuesta oficial"),
) -> QFilters:
    return QFilters(
        subject=subject,
        topic=topic,
        document_id=document_id,
        has_diagram=has_diagram,
        exam=exam,
        exam_type=exam_type,
        page_from=page_from,
        page_to=page_to,
        difficulty=difficulty,
        has_answer=has_answer,
    )


def _has_solution() -> ColumnElement:
    return exists().where(QuestionSolution.question_id == Question.id, QuestionSolution.status == "done")


def _to_out(
    qn: Question, filename: str, pdf_path: str, rank: float | None = None, has_solution: bool = False
) -> QuestionOut:
    return QuestionOut(
        id=qn.id,
        document_id=qn.document_id,
        document_filename=filename,
        question_number=qn.question_number,
        question_label=qn.question_label,
        page_number=qn.page_number,
        page_image_path=qn.page_image_path,
        subject=qn.subject,
        topic=qn.topic,
        statement=qn.statement,
        options=qn.options or [],
        has_diagram=qn.has_diagram,
        exam=qn.exam,
        exam_type=qn.exam_type,
        exam_year=qn.exam_year,
        answer=qn.answer,
        answer_detail=qn.answer_detail,
        difficulty=qn.difficulty,
        key_note=qn.key_note,
        has_solution=bool(has_solution),
        figures=qn.figures or [],
        rank=rank,
        pdf_path=pdf_path,
    )


@router.get("/questions", response_model=QuestionPage)
async def search_questions(
    f: QFilters = Depends(_filters_dep),
    q: str | None = Query(None, description="Palabras clave (full-text en español)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> QuestionPage:
    tsq = build_tsquery(q) if q else None
    rank = func.ts_rank(Question.search_vector, tsq) if tsq is not None else literal(None)

    stmt = select(
        Question,
        Document.filename.label("document_filename"),
        Document.file_path.label("pdf_path"),
        rank.label("rank"),
        _has_solution().label("has_solution"),
    ).join(Document, Document.id == Question.document_id)
    stmt = _apply_filters(stmt, f)
    if tsq is not None:
        stmt = stmt.where(Question.search_vector.op("@@")(tsq))

    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    total = total or 0

    order = [Question.document_id, Question.page_number, Question.question_number, Question.id]
    if tsq is not None:
        order.insert(0, rank.desc())
    rows = (await session.execute(stmt.order_by(*order).offset((page - 1) * limit).limit(limit))).all()

    items = [
        _to_out(
            row.Question,
            row.document_filename,
            row.pdf_path,
            float(row.rank) if row.rank is not None else None,
            row.has_solution,
        )
        for row in rows
    ]
    return QuestionPage(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=max(1, math.ceil(total / limit)),
    )


@router.get("/questions/{question_id}", response_model=QuestionOut)
async def get_question(question_id: int, session: AsyncSession = Depends(get_session)) -> QuestionOut:
    row = (
        await session.execute(
            select(Question, Document.filename, Document.file_path, _has_solution())
            .join(Document, Document.id == Question.document_id)
            .where(Question.id == question_id)
        )
    ).first()
    if not row:
        raise HTTPException(404, "Pregunta no encontrada")
    qn, filename, pdf_path, has_solution = row
    return _to_out(qn, filename, pdf_path, has_solution=has_solution)


@router.get("/filters", response_model=FiltersOut)
async def get_filters(
    f: QFilters = Depends(_filters_dep),
    session: AsyncSession = Depends(get_session),
) -> FiltersOut:
    """
    Opciones de filtro con contadores. Cada grupo se cuenta con los demás filtros activos,
    pero sin su propio filtro (así se puede cambiar de materia/examen sin perder opciones).
    """
    count = func.count(Question.id)

    subj_f = f.without("subject", "topic")
    subjects = [
        SubjectCount(subject=s, count=c)
        for s, c in (
            await session.execute(
                _apply_filters(select(Question.subject, count).group_by(Question.subject), subj_f).order_by(
                    count.desc()
                )
            )
        ).all()
    ]

    topics: dict[str, list[TopicCount]] = {}
    topic_stmt = _apply_filters(
        select(Question.subject, Question.topic, count).group_by(Question.subject, Question.topic),
        subj_f,
    )
    for s, t, c in (await session.execute(topic_stmt.order_by(Question.subject, count.desc(), Question.topic))).all():
        topics.setdefault(s, []).append(TopicCount(topic=t, count=c))

    exam_f = f.without("exam", "exam_type")
    exam_types = [
        ExamTypeCount(exam_type=t, count=c)
        for t, c in (
            await session.execute(
                _apply_filters(
                    select(Question.exam_type, count).where(Question.exam_type != "").group_by(Question.exam_type),
                    exam_f,
                ).order_by(count.desc())
            )
        ).all()
    ]
    exam_rows_f = f.without("exam")
    exams = [
        ExamCount(exam=e, exam_type=t, exam_year=y, first_page=p0, last_page=p1, count=c)
        for e, t, y, p0, p1, c in (
            await session.execute(
                _apply_filters(
                    select(
                        Question.exam,
                        Question.exam_type,
                        func.max(Question.exam_year),
                        func.min(Question.page_number),
                        func.max(Question.page_number),
                        count,
                    )
                    .where(Question.exam != "")
                    .group_by(Question.exam, Question.exam_type),
                    exam_rows_f,
                ).order_by(func.min(Question.page_number))
            )
        ).all()
    ]

    difficulties = [
        DifficultyCount(difficulty=d, count=c)
        for d, c in (
            await session.execute(
                _apply_filters(
                    select(Question.difficulty, count).where(Question.difficulty > 0).group_by(Question.difficulty),
                    f.without("difficulty"),
                ).order_by(Question.difficulty)
            )
        ).all()
    ]

    base = f.without("subject", "topic", "page_from", "page_to")
    agg = (
        await session.execute(
            _apply_filters(
                select(
                    func.count(Question.id).filter(Question.has_diagram.is_(True)),
                    func.count(Question.id).filter(Question.answer != ""),
                    func.min(Question.page_number),
                    func.max(Question.page_number),
                ),
                base.without("has_diagram", "has_answer"),
            )
        )
    ).one()

    return FiltersOut(
        total=sum(s.count for s in subjects),
        diagram_count=agg[0] or 0,
        answered_count=agg[1] or 0,
        page_min=agg[2] or 0,
        page_max=agg[3] or 0,
        subjects=subjects,
        topics=topics,
        exam_types=exam_types,
        exams=exams,
        difficulties=difficulties,
    )
