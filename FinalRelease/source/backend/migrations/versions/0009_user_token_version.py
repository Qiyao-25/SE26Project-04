"""add token versioning for password-change revocation

Revision ID: 0009_user_token_version
Revises: 0008_remove_default_admin
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_user_token_version"
down_revision = "0008_remove_default_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("users", "token_version")
