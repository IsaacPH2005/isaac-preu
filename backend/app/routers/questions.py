import math
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ColumnElement, Select, and_, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Document, Question
from app.schemas import FiltersOut, QuestionOut, QuestionPage, SubjectCount, TopicCount
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


def _apply_filters(
    stmt: Select,
    *,
    subject: str | None = None,
    topic: str | None = None,
    document_id: int | None = None,
    has_diagram: bool | None = None,
) -> Select:
    conds = []
    if subject:
        conds.append(Question.subject == subject)
    if topic:
        conds.append(Question.topic == topic)
    if document_id:
        conds.append(Question.document_id == document_id)
    if has_diagram:
        conds.append(Question.has_diagram.is_(True))
    return stmt.where(and_(*conds)) if conds else stmt


@router.get("/questions", response_model=QuestionPage)
async def search_questions(
    subject: str | None = Query(None, description="Materia, ej. FISICA"),
    topic: str | None = Query(None, description="Tema exacto"),
    q: str | None = Query(None, description="Palabras clave (full-text en español)"),
    document_id: int | None = Query(None),
    has_diagram: bool | None = Query(None, description="Solo preguntas con gráficos"),
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
    ).join(Document, Document.id == Question.document_id)
    stmt = _apply_filters(
        stmt, subject=subject, topic=topic, document_id=document_id, has_diagram=has_diagram
    )
    if tsq is not None:
        stmt = stmt.where(Question.search_vector.op("@@")(tsq))

    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    total = total or 0

    order = [Question.document_id, Question.page_number, Question.question_number, Question.id]
    if tsq is not None:
        order.insert(0, rank.desc())
    rows = (await session.execute(stmt.order_by(*order).offset((page - 1) * limit).limit(limit))).all()

    items = [
        QuestionOut(
            id=row.Question.id,
            document_id=row.Question.document_id,
            document_filename=row.document_filename,
            question_number=row.Question.question_number,
            page_number=row.Question.page_number,
            page_image_path=row.Question.page_image_path,
            subject=row.Question.subject,
            topic=row.Question.topic,
            statement=row.Question.statement,
            options=row.Question.options or [],
            has_diagram=row.Question.has_diagram,
            rank=float(row.rank) if row.rank is not None else None,
            pdf_path=row.pdf_path,
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
            select(Question, Document.filename, Document.file_path)
            .join(Document, Document.id == Question.document_id)
            .where(Question.id == question_id)
        )
    ).first()
    if not row:
        raise HTTPException(404, "Pregunta no encontrada")
    qn, filename, pdf_path = row
    return QuestionOut(
        id=qn.id,
        document_id=qn.document_id,
        document_filename=filename,
        question_number=qn.question_number,
        page_number=qn.page_number,
        page_image_path=qn.page_image_path,
        subject=qn.subject,
        topic=qn.topic,
        statement=qn.statement,
        options=qn.options or [],
        has_diagram=qn.has_diagram,
        pdf_path=pdf_path,
    )


@router.get("/filters", response_model=FiltersOut)
async def get_filters(
    document_id: int | None = Query(None),
    has_diagram: bool | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> FiltersOut:
    base_kwargs = {"document_id": document_id, "has_diagram": has_diagram}

    subj_stmt = _apply_filters(
        select(Question.subject, func.count(Question.id)).group_by(Question.subject), **base_kwargs
    )
    subjects = [
        SubjectCount(subject=s, count=c)
        for s, c in (await session.execute(subj_stmt.order_by(func.count(Question.id).desc()))).all()
    ]

    topic_stmt = _apply_filters(
        select(Question.subject, Question.topic, func.count(Question.id)).group_by(
            Question.subject, Question.topic
        ),
        **base_kwargs,
    )
    topics: dict[str, list[TopicCount]] = {}
    for s, t, c in (
        await session.execute(topic_stmt.order_by(Question.subject, func.count(Question.id).desc(), Question.topic))
    ).all():
        topics.setdefault(s, []).append(TopicCount(topic=t, count=c))

    diagram_stmt = _apply_filters(
        select(func.count(Question.id)), document_id=document_id, has_diagram=True
    )
    diagram_count = await session.scalar(diagram_stmt) or 0

    return FiltersOut(
        total=sum(s.count for s in subjects),
        diagram_count=diagram_count,
        subjects=subjects,
        topics=topics,
    )
