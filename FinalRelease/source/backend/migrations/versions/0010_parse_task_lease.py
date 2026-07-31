"""add ownership marker for in-process parse execution

Revision ID: 0010_parse_task_lease
Revises: 0009_user_token_version
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_parse_task_lease"
down_revision = "0009_user_token_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parse_tasks", sa.Column("lease_token", sa.String(length=128), nullable=True))
    op.create_index("ix_parse_tasks_lease_token", "parse_tasks", ["lease_token"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_parse_tasks_lease_token", table_name="parse_tasks")
    op.drop_column("parse_tasks", "lease_token")
