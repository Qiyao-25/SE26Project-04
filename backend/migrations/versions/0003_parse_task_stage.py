"""add parse task stage"""

from alembic import op
import sqlalchemy as sa


revision = "0003_parse_task_stage"
down_revision = "0002_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parse_tasks", sa.Column("stage", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("parse_tasks", "stage")
