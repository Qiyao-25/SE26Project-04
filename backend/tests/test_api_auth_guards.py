"""Protected write/task endpoints require authentication."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _app(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'auth.db').as_posix()}",
        auth_secret="test-secret",
        enable_docs=False,
    )
    return create_app(settings)


def test_parse_requires_login(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        resp = client.post("/api/papers/1/parse", json={"task_type": "full_parse", "force": False}, headers={"Idempotency-Key": "k1"})
        assert resp.status_code == 401


def test_batch_requires_admin(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        resp = client.post("/api/papers/batch", json=[])
        assert resp.status_code == 401


def test_enqueue_pending_requires_admin(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        resp = client.post("/api/tasks/enqueue-pending")
        assert resp.status_code == 401


def test_task_detail_requires_login(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        resp = client.get("/api/tasks/1")
        assert resp.status_code == 401
