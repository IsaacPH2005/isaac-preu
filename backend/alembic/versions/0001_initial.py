"""Esquema inicial: documents, questions, búsqueda full-text en español.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # unaccent permite que "fisica" encuentre "física" y viceversa.
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # unaccent() no es IMMUTABLE; este wrapper sí, para poder usarlo en índices/triggers.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text AS
        $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        """
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_documents_status",
        ),
    )
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("page_image_path", sa.String(1024), nullable=False),
        sa.Column("subject", sa.String(64), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False, server_default="General"),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "options",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("has_diagram", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.create_index("ix_questions_document_id", "questions", ["document_id"])
    op.create_index("ix_questions_subject", "questions", ["subject"])
    op.create_index("ix_questions_has_diagram", "questions", ["has_diagram"])
    op.create_index("ix_questions_subject_topic", "questions", ["subject", "topic"])
    op.create_index(
        "ix_questions_doc_page_number",
        "questions",
        ["document_id", "page_number", "question_number"],
    )
    op.create_index(
        "ix_questions_search_vector",
        "questions",
        ["search_vector"],
        postgresql_using="gin",
    )

    # Trigger que mantiene search_vector actualizado (materia y tema pesan más).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION questions_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('spanish', f_unaccent(replace(coalesce(NEW.subject, ''), '_', ' '))), 'A') ||
                setweight(to_tsvector('spanish', f_unaccent(coalesce(NEW.topic, ''))), 'A') ||
                setweight(to_tsvector('spanish', f_unaccent(coalesce(NEW.statement, ''))), 'B') ||
                setweight(to_tsvector('spanish', f_unaccent(coalesce(NEW.options::text, ''))), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_questions_search_vector
        BEFORE INSERT OR UPDATE OF subject, topic, statement, options ON questions
        FOR EACH ROW EXECUTE FUNCTION questions_search_vector_update()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_questions_search_vector ON questions")
    op.execute("DROP FUNCTION IF EXISTS questions_search_vector_update()")
    op.drop_table("questions")
    op.drop_table("documents")
    op.execute("DROP FUNCTION IF EXISTS f_unaccent(text)")
