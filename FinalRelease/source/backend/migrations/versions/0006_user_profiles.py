"""add persisted user reading profiles"""

from alembic import op
import sqlalchemy as sa


revision = "0006_user_profiles"
down_revision = "0005_backfill_qa_ready"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(length=128), primary_key=True),
        sa.Column("persona", sa.String(length=32), nullable=False, server_default="研究"),
        sa.Column("topics", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
