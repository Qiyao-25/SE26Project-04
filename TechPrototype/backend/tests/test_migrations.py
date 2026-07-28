import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _run_migration(database_url: str, *args: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "PAPERMATE_ENV": "test",
            "PAPERMATE_DATABASE_URL": database_url,
        }
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_sqlite_migrations_upgrade_downgrade_and_remove_default_admin(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"

    _run_migration(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "owner_user_id" in {column["name"] for column in inspector.get_columns("parse_tasks")}
    assert any(fk["name"] == "fk_parse_tasks_owner_user_id" for fk in inspector.get_foreign_keys("parse_tasks"))

    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM users WHERE email = 'admin'").scalar_one() == 0

    _run_migration(database_url, "downgrade", "0010_parse_task_lease")
    assert "owner_user_id" not in {column["name"] for column in inspect(engine).get_columns("parse_tasks")}

    _run_migration(database_url, "upgrade", "head")
    assert "owner_user_id" in {column["name"] for column in inspect(engine).get_columns("parse_tasks")}
