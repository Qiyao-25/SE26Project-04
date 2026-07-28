"""Create or promote an administrator without storing a default password."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import User
from app.service.auth import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a PaperMate administrator")
    parser.add_argument("--email", required=True, help="管理员登录名或邮箱")
    args = parser.parse_args()
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password or password != confirm or len(password) < 6:
        raise SystemExit("密码为空、两次输入不一致或长度少于 6 位")

    settings = Settings()
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_config, "head")
    engine = create_engine_for(settings)
    email = args.email.strip().casefold()
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, role="admin", password_hash=hash_password(password))
            session.add(user)
        else:
            user.role = "admin"
            user.is_active = True
            user.password_hash = hash_password(password)
            user.token_version += 1
        session.commit()
    print(f"administrator ready: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
