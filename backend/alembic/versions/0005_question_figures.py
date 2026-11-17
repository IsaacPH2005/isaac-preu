"""figuras recortadas de cada pregunta

Revision ID: 0005_question_figures
Revises: 0004_question_solutions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_question_figures"
down_revision = "0004_question_solutions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rutas (relativas a STORAGE_DIR) de las figuras recortadas de la pregunta
    op.add_column("questions", sa.Column("figures", JSONB(), nullable=False, server_default="[]"))
    # Caja de la figura que indica la IA en páginas escaneadas: [ymin, xmin, ymax, xmax] en 0-1000
    op.add_column("questions", sa.Column("figure_box", JSONB(), nullable=True))
    # Datos leídos de la figura por la IA al resolver
    op.add_column(
        "question_solutions", sa.Column("figure_data", JSONB(), nullable=False, server_default="[]")
    )
    # Las soluciones de preguntas con figura se generaron sin ver la figura recortada: se descartan
    op.execute(
        "DELETE FROM question_solutions s USING questions q WHERE q.id = s.question_id AND q.has_diagram"
    )


def downgrade() -> None:
    op.drop_column("question_solutions", "figure_data")
    op.drop_column("questions", "figure_box")
    op.drop_column("questions", "figures")
