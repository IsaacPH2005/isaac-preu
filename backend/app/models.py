from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DOCUMENT_STATUSES = ("pending", "processing", "completed", "failed")


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_documents_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    questions: Mapped[list["Question"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_questions_subject_topic", "subject", "topic"),
        Index("ix_questions_doc_page_number", "document_id", "page_number", "question_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_label: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_image_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, default="General")
    statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    options: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    has_diagram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    # Examen de origen, ej. "Segundo examen de ingreso 1-2012" (tipo: "Segunda opción", año: 2012)
    exam: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    exam_type: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    exam_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Respuesta oficial desde la clave (tabla answer_key)
    answer: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    answer_detail: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    key_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Figuras recortadas (rutas relativas a STORAGE_DIR) y caja indicada por la IA en páginas escaneadas
    figures: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    figure_box: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    # Mantenido por el trigger trg_questions_search_vector (ver migración inicial).
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    document: Mapped[Document] = relationship(back_populates="questions")


class AnswerKeyRow(Base):
    """Fila de la clave oficial: (página impresa, número de pregunta) -> respuesta."""

    __tablename__ = "answer_key"
    __table_args__ = (Index("ix_answer_key_page_number", "page", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    prefix: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    answer: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    detail: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    readable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")


SOLUTION_STATUSES = ("pending", "done", "failed")


class QuestionSolution(Base):
    """Solución generada por IA (estrategia, pasos y tips). Se genera una vez y se reutiliza."""

    __tablename__ = "question_solutions"

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    figure_data: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    strategy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    steps: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    shortcut: Mapped[str] = mapped_column(Text, nullable=False, default="")
    common_mistake: Mapped[str] = mapped_column(Text, nullable=False, default="")
    final_answer: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    reaches_key: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
