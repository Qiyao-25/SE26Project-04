"""remove the insecure migration-created admin account

Revision ID: 0008_remove_default_admin
Revises: 0007_users
"""

import hashlib

from alembic import op
import sqlalchemy as sa


revision = "0008_remove_default_admin"
down_revision = "0007_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    salt = b"papermate-demo-admin"
    digest = hashlib.pbkdf2_hmac("sha256", b"admin123", salt, 120_000).hex()
    password_hash = f"120000${salt.hex()}${digest}"
    users = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("password_hash", sa.String),
    )
    op.execute(
        users.delete().where(
            sa.and_(users.c.email == "admin", users.c.password_hash == password_hash)
        )
    )


def downgrade() -> None:
    # Intentionally do not recreate a known weak credential on downgrade.
    pass
