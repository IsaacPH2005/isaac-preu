"""etiqueta impresa de la pregunta (A1, G3, Q-13)

Revision ID: 0003_question_label
Revises: 0002_exams_answer_key
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_question_label"
down_revision = "0002_exams_answer_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("question_label", sa.String(16), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("questions", "question_label")
