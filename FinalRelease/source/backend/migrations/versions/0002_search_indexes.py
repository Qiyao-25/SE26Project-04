"""add paper search indexes

Revision ID: 0002_search_indexes
Revises: 0001_initial_schema
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_search_indexes"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_papers_published_at", "papers", ["published_at"], unique=False)
    op.create_index("ix_parse_tasks_paper_status_requested", "parse_tasks", ["paper_id", "status", "requested_at"], unique=False)
    op.create_index("ix_paper_authors_author_id", "paper_authors", ["author_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_paper_authors_author_id", table_name="paper_authors")
    op.drop_index("ix_parse_tasks_paper_status_requested", table_name="parse_tasks")
    op.drop_index("ix_papers_published_at", table_name="papers")
