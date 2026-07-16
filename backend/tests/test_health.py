from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_returns_unified_response_and_request_id() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite:///:memory:"))
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-request"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    body = response.json()
    assert body["code"] == "OK"
    assert body["request_id"] == "test-request"
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] == "ok"


def test_openapi_exposes_health_endpoint() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite:///:memory:"))
    with TestClient(app) as client:
        openapi = client.get("/openapi.json").json()
    assert "/health" in openapi["paths"]
    assert openapi["info"]["title"] == "PaperMate Backend API"

