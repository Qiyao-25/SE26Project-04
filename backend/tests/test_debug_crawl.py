"""DEBUG crawl route registration and authorization tests."""

from app.core.auth import require_admin
from app.core.config import Settings
from app.main import create_app


def _route(app):
    routes = [
        route
        for included in app.routes
        for route in getattr(getattr(included, "original_router", None), "routes", [])
    ]
    return next(route for route in routes if route.path == "/api/debug/crawl/run")


def test_debug_crawl_hidden_when_disabled(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 't.db'}",
        auth_secret="test-secret",
        enable_crawl_debug=False,
        enable_docs=False,
    )
    app = create_app(settings)
    assert all(
        route.path != "/api/debug/crawl/run"
        for included in app.routes
        for route in getattr(getattr(included, "original_router", None), "routes", [])
    )


def test_debug_crawl_requires_admin_when_enabled(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 't2.db'}",
        auth_secret="test-secret",
        enable_crawl_debug=True,
        enable_docs=False,
    )
    route = _route(create_app(settings))
    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
    assert require_admin in dependency_calls
