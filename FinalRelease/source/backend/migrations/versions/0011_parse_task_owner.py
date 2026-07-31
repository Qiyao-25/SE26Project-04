"""associate user-created parse tasks with their owner

Revision ID: 0011_parse_task_owner
Revises: 0010_parse_task_lease
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_parse_task_owner"
down_revision = "0010_parse_task_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot add a foreign key to an existing table with ALTER TABLE.
    # batch_alter_table recreates the table on SQLite and uses normal ALTER
    # statements on PostgreSQL.
    with op.batch_alter_table("parse_tasks", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_parse_tasks_owner_user_id",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_parse_tasks_owner_user_id", "parse_tasks", ["owner_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_parse_tasks_owner_user_id", table_name="parse_tasks")
    with op.batch_alter_table("parse_tasks", recreate="auto") as batch_op:
        batch_op.drop_constraint("fk_parse_tasks_owner_user_id", type_="foreignkey")
        batch_op.drop_column("owner_user_id")
