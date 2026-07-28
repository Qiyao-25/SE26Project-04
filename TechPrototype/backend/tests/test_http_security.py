from types import SimpleNamespace

from fastapi.responses import JSONResponse
from starlette.requests import Request
from sqlalchemy.orm import Session

from app.api.auth import account_update, auth_me, auth_register
from app.api.search import search_chunks_api
from app.api.tasks import task_detail
from app.core.config import Settings
from app.core.database import create_engine_for
from app.core.auth import require_current_user
from app.main import create_app
from app.model import Base
from app.schema.auth import AccountUpdate, AuthUser, RegisterRequest
from app.schema.papers import ChunkSearchRequest, PaperUpsert
from app.service.papers import batch_upsert_papers
from app.service.tasks import create_task


def make_app_and_request(path: str, method: str = "GET"):
    settings = Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        auth_secret="test-secret",
        enable_docs=False,
        crawl_enabled=False,
        parse_scheduler_enabled=False,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "client": ("test", 0),
        "server": ("test", 80),
        "scheme": "http",
        "query_string": b"",
        "root_path": "",
        "app": SimpleNamespace(state=SimpleNamespace(settings=settings, engine=app.state.engine)),
    }
    request = Request(scope)
    request.state.request_id = "security-test-request"
    return app, request


def bearer(token: str) -> str:
    return f"Bearer {token}"


def _route(app, path: str, method: str):
    """Find routes mounted by create_app, including APIRouter wrappers."""
    for included in app.routes:
        for route in getattr(getattr(included, "original_router", None), "routes", []):
            if route.path == path and method in route.methods:
                return route
    raise AssertionError(f"route not found: {method} {path}")


def test_route_functions_enforce_task_ownership_and_search_auth_contract() -> None:
    app, request = make_app_and_request("/api/auth/register", "POST")
    with Session(app.state.engine) as session:
        first = auth_register(
            RegisterRequest(email="reader-a@example.com", password="password123"),
            request,
            session,
        )
        second = auth_register(
            RegisterRequest(email="reader-b@example.com", password="password123"),
            request,
            session,
        )
        token_a = first.data.access_token
        token_b = second.data.access_token
        user_a = int(first.data.user.user_id)
        user_b = int(second.data.user.user_id)

        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="security-paper", title="Security Paper")],
        ).items[0].paper_id
        task, _ = create_task(
            session,
            paper_id,
            "full_parse",
            "security-task",
            owner_user_id=user_a,
        )

        own = task_detail(
            task.task_id,
            request,
            session,
            AuthUser(user_id=str(user_a), email="reader-a@example.com", role="user"),
        )
        other = task_detail(
            task.task_id,
            request,
            session,
            AuthUser(user_id=str(user_b), email="reader-b@example.com", role="user"),
        )
        assert own.data.owner_user_id == user_a
        assert isinstance(other, JSONResponse)
        assert other.status_code == 403

        search = search_chunks_api(
            ChunkSearchRequest(query="attention", paper_id=paper_id),
            request,
            AuthUser(user_id=str(user_a), email="reader-a@example.com", role="user"),
            session,
        )
        assert search.data.chunks == []

        assert auth_me(request, authorization=bearer(token_a), db=session).data.user_id == str(user_a)
        unauthenticated = auth_me(request, authorization=None, db=session)
        assert isinstance(unauthenticated, JSONResponse)
        assert unauthenticated.status_code == 401


def test_password_change_revokes_old_token() -> None:
    app, request = make_app_and_request("/api/auth/register", "POST")
    with Session(app.state.engine) as session:
        registered = auth_register(
            RegisterRequest(email="password-reader@example.com", password="password123"),
            request,
            session,
        )
        old_token = registered.data.access_token
        changed = account_update(
            AccountUpdate(current_password="password123", password="new-password123"),
            request,
            authorization=bearer(old_token),
            db=session,
        )
        new_token = changed.data.access_token
        old_me = auth_me(request, authorization=bearer(old_token), db=session)
        new_me = auth_me(request, authorization=bearer(new_token), db=session)
        assert isinstance(old_me, JSONResponse)
        assert old_me.status_code == 401
        assert new_me.data.user_id == registered.data.user.user_id


def test_search_route_declares_login_dependency() -> None:
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite:///:memory:",
            auth_secret="test-secret",
            enable_docs=False,
        )
    )
    route = _route(app, "/api/search/chunks", "POST")
    dependencies = {dependency.call for dependency in route.dependant.dependencies}
    assert require_current_user in dependencies
