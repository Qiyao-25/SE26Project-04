from app.core.config import Settings
from app.core.database import create_engine_for
from app.main import create_app
from app.service.health import get_health


def test_health_returns_unified_response_and_request_id() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite:///:memory:"))
    data = get_health(app.state.engine, app.state.settings)
    assert data.status == "ok"
    assert data.database == "ok"


def test_openapi_exposes_health_endpoint() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite:///:memory:"))
    openapi = app.openapi()
    assert "/health" in openapi["paths"]
    assert "/api/papers" in openapi["paths"]
    assert openapi["info"]["title"] == "PaperMate Backend API"
