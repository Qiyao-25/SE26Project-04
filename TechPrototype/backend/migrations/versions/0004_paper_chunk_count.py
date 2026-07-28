"""track paper text chunk readiness"""

from alembic import op
import sqlalchemy as sa


revision = "0004_paper_chunk_count"
down_revision = "0003_parse_task_stage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("papers", sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        "UPDATE papers SET chunk_count = "
        "(SELECT COUNT(*) FROM text_chunks WHERE text_chunks.paper_id = papers.id)"
    )


def downgrade() -> None:
    op.drop_column("papers", "chunk_count")
