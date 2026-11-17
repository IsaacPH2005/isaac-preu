"""soluciones y estrategias generadas por IA (una por pregunta, en caché)

Revision ID: 0004_question_solutions
Revises: 0003_question_label
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_question_solutions"
down_revision = "0003_question_label"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_solutions",
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("strategy", sa.Text(), nullable=False, server_default=""),
        sa.Column("steps", JSONB(), nullable=False, server_default="[]"),
        sa.Column("shortcut", sa.Text(), nullable=False, server_default=""),
        sa.Column("common_mistake", sa.Text(), nullable=False, server_default=""),
        sa.Column("final_answer", sa.String(8), nullable=False, server_default=""),
        sa.Column("reaches_key", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.String(8), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("question_solutions")
