from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_image_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, default="General")
    statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    options: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    has_diagram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    # Mantenido por el trigger trg_questions_search_vector (ver migración inicial).
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    document: Mapped[Document] = relationship(back_populates="questions")
