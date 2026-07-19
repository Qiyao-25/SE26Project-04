from types import SimpleNamespace

from starlette.requests import Request
from sqlalchemy.orm import Session

from app.api.admin import overview, quality
from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base


def make_request(settings, engine) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/admin/overview",
        "headers": [],
        "client": ("test", 0),
        "server": ("test", 80),
        "scheme": "http",
        "query_string": b"",
        "root_path": "",
        "app": SimpleNamespace(state=SimpleNamespace(settings=settings, engine=engine)),
    }
    request = Request(scope)
    request.state.request_id = "admin-test-request"
    return request


def test_admin_overview_and_quality_routes_return_data() -> None:
    settings = Settings(environment="test", database_url="sqlite:///:memory:")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        request = make_request(settings, engine)
        overview_response = overview(request, None, session)
        quality_response = quality(request, limit=10, _admin=None, db=session)

    assert overview_response.data["metrics"]["papers"] == 0
    assert quality_response.data["exceptions"] == []
    assert quality_response.data["rates"]["抓取"] == 0
