"""examen de origen, respuestas oficiales y tabla de clave

Revision ID: 0002_exams_answer_key
Revises: 0001_initial
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_exams_answer_key"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Examen al que pertenece cada pregunta (encabezado heredado entre páginas)
    op.add_column("questions", sa.Column("exam", sa.String(255), nullable=False, server_default=""))
    op.add_column("questions", sa.Column("exam_type", sa.String(64), nullable=False, server_default=""))
    op.add_column("questions", sa.Column("exam_year", sa.Integer(), nullable=True))
    # Respuesta oficial (desde la clave)
    op.add_column("questions", sa.Column("answer", sa.String(8), nullable=False, server_default=""))
    op.add_column("questions", sa.Column("answer_detail", sa.String(255), nullable=False, server_default=""))
    op.add_column("questions", sa.Column("difficulty", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("questions", sa.Column("key_note", sa.Text(), nullable=False, server_default=""))
    op.create_index("ix_questions_exam", "questions", ["exam"])
    op.create_index("ix_questions_exam_type", "questions", ["exam_type"])
    op.create_index("ix_questions_page_number", "questions", ["page_number"])

    op.create_table(
        "answer_key",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject", sa.String(64), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False, server_default=""),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("prefix", sa.String(8), nullable=False, server_default=""),
        sa.Column("answer", sa.String(8), nullable=False, server_default=""),
        sa.Column("detail", sa.String(255), nullable=False, server_default=""),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("readable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_answer_key_page_number", "answer_key", ["page", "number"])

    # El examen también se puede buscar por texto ("parcial 2024", "única opción")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION questions_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('spanish', f_unaccent(replace(coalesce(NEW.subject, ''), '_', ' '))), 'A') ||
                setweight(to_tsvector('spanish', f_unaccent(coalesce(NEW.topic, ''))), 'A') ||
                setweight(to_tsvector('spanish', f_unaccent(coalesce(NEW.exam, ''))), 'B') ||
                setweight(to_tsvector('spanish', f_unaccent(coalesce(NEW.statement, ''))), 'B') ||
                setweight(to_tsvector('spanish', f_unaccent(coalesce(NEW.options::text, ''))), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_questions_search_vector ON questions")
    op.execute(
        """
        CREATE TRIGGER trg_questions_search_vector
        BEFORE INSERT OR UPDATE OF subject, topic, exam, statement, options ON questions
        FOR EACH ROW EXECUTE FUNCTION questions_search_vector_update()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_questions_search_vector ON questions")
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
    op.drop_index("ix_answer_key_page_number", table_name="answer_key")
    op.drop_table("answer_key")
    op.drop_index("ix_questions_page_number", table_name="questions")
    op.drop_index("ix_questions_exam_type", table_name="questions")
    op.drop_index("ix_questions_exam", table_name="questions")
    for col in ("key_note", "difficulty", "answer_detail", "answer", "exam_year", "exam_type", "exam"):
        op.drop_column("questions", col)
