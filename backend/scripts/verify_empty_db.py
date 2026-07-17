"""Verify migration, 100-row seed import, health and OpenAPI on a clean DB."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.config import Settings
from app.core.database import create_engine_for
from app.main import create_app
from app.model import Base, Paper
from app.service.health import get_health
from app.service.papers import search_papers
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=Path("../PaperPipeline/data/seed.json"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="papermate-empty-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'acceptance.db'}"
        env = {**os.environ, "PAPERMATE_DATABASE_URL": database_url}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
        subprocess.run([sys.executable, "-m", "scripts.import_seed", "--seed", str(args.seed)], check=True, env=env)
        app = create_app(Settings(environment="test", database_url=database_url))
        health = get_health(app.state.engine, app.state.settings)
        with Session(create_engine_for(Settings(environment="test", database_url=database_url))) as session:
            total = session.scalar(select(func.count(Paper.id))) or 0
            page = search_papers(
                session,
                keyword="Transformer",
                author=None,
                category=None,
                published_from=None,
                published_to=None,
                page=1,
                page_size=1,
            )
        openapi = app.openapi()
        assert health.database == "ok"
        assert total >= 100
        assert page.total >= 1
        assert "/api/search/chunks" in openapi["paths"]
        print(f"empty_db_acceptance=PASS papers={total} search_matches={page.total}")


if __name__ == "__main__":
    main()
