"""DEBUG crawl endpoint tests — delete with app/api/debug_crawl.py."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_debug_crawl_hidden_when_disabled(tmp_path):
    db_path = tmp_path / "t.db"
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{db_path.as_posix()}",
        auth_secret="test-secret",
        enable_crawl_debug=False,
        enable_docs=False,
    )
    client = TestClient(create_app(settings))
    resp = client.post("/api/debug/crawl/run")
    assert resp.status_code == 404


def test_debug_crawl_requires_auth_when_enabled(tmp_path):
    db_path = tmp_path / "t2.db"
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{db_path.as_posix()}",
        auth_secret="test-secret",
        enable_crawl_debug=True,
        enable_docs=False,
    )
    client = TestClient(create_app(settings))
    resp = client.post("/api/debug/crawl/run")
    assert resp.status_code == 401
