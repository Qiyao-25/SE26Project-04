from pathlib import Path

from app.core.config import BACKEND_DIR, Settings


def test_default_runtime_paths_are_rooted_at_backend_directory():
    settings = Settings(environment="test", database_url="sqlite:///./data/dev.db", paper_storage_dir="data/pdfs")

    assert settings.database_url == f"sqlite:///{(BACKEND_DIR / 'data' / 'dev.db').as_posix()}"
    assert Path(settings.paper_storage_dir) == (BACKEND_DIR / "data" / "pdfs").resolve()
