"""backfill qa-ready status for parsed papers with text chunks"""

from alembic import op


revision = "0005_backfill_qa_ready"
down_revision = "0004_paper_chunk_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE papers SET ingest_status = 'qa_ready' "
        "WHERE ingest_status = 'parsed' AND chunk_count > 0"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE papers SET ingest_status = 'parsed' "
        "WHERE ingest_status = 'qa_ready' AND chunk_count > 0"
    )
