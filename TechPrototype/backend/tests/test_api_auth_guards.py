"""Protected write/task endpoints declare the expected access controls."""

from app.core.auth import require_admin, require_current_user
from app.core.config import Settings
from app.main import create_app


def _route(app, path: str, method: str):
    for included in app.routes:
        for route in getattr(getattr(included, "original_router", None), "routes", []):
            if route.path == path and method in route.methods:
                return route
    raise AssertionError(f"route not found: {method} {path}")


def _dependencies(route) -> set:
    return {dependency.call for dependency in route.dependant.dependencies}


def _app(tmp_path):
    return create_app(
        Settings(
            environment="test",
            database_url=f"sqlite:///{(tmp_path / 'auth.db').as_posix()}",
            auth_secret="test-secret",
            enable_docs=False,
        )
    )


def test_parse_requires_login(tmp_path):
    assert require_current_user in _dependencies(_route(_app(tmp_path), "/api/papers/{paper_id}/parse", "POST"))


def test_batch_requires_admin(tmp_path):
    assert require_admin in _dependencies(_route(_app(tmp_path), "/api/papers/batch", "POST"))


def test_enqueue_pending_requires_admin(tmp_path):
    assert require_admin in _dependencies(_route(_app(tmp_path), "/api/tasks/enqueue-pending", "POST"))


def test_task_detail_requires_login(tmp_path):
    assert require_current_user in _dependencies(_route(_app(tmp_path), "/api/tasks/{task_id}", "GET"))
