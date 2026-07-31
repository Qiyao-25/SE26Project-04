"""add users for backend-backed login"""

import hashlib

from alembic import op
import sqlalchemy as sa


revision = "0007_users"
down_revision = "0006_user_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    salt = b"papermate-demo-admin"
    digest = hashlib.pbkdf2_hmac("sha256", b"admin123", salt, 120_000).hex()
    password_hash = f"120000${salt.hex()}${digest}"
    op.bulk_insert(
        sa.table(
            "users",
            sa.column("email", sa.String),
            sa.column("password_hash", sa.String),
            sa.column("role", sa.String),
        ),
        [{"email": "admin", "password_hash": password_hash, "role": "admin"}],
    )


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
