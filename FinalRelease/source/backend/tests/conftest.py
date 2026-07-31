"""Shared pytest fixtures for PaperMate backend HTTP and service tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.main import create_app
from app.model import Base, User
from app.schema.papers import AuthorInput, PaperUpsert
from app.service.auth import hash_password
from app.service.papers import batch_upsert_papers


@pytest.fixture
def settings(tmp_path) -> Settings:
    db_path = (tmp_path / "test.db").as_posix()
    return Settings(
        environment="test",
        database_url=f"sqlite:///{db_path}",
        auth_secret="test-secret",
        worker_token="test-worker-token",
        crawl_enabled=False,
        parse_scheduler_enabled=False,
        enable_docs=True,
        paper_storage_dir=str(tmp_path / "pdfs"),
        parse_agent_enabled=False,
        qa_agent_enabled=True,
        llm_api_key="test-key",
        llm_model="test-model",
    )


@pytest.fixture
def app(settings: Settings, monkeypatch):
    async def _noop_scheduler(app, stop_event):
        await stop_event.wait()

    monkeypatch.setattr("app.main.run_crawl_scheduler", _noop_scheduler)
    monkeypatch.setattr("app.main.run_parse_scheduler", _noop_scheduler)
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    return application


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session(app) -> Generator[Session, None, None]:
    with Session(app.state.engine) as session:
        yield session


def register_user(
    client: TestClient,
    *,
    email: str = "reader@example.com",
    password: str = "password123",
) -> dict:
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_admin(db_session: Session, *, email: str = "admin@example.com", password: str = "adminpass123") -> User:
    existing = db_session.query(User).filter(User.email == email).one_or_none()
    if existing is not None:
        existing.role = "admin"
        existing.password_hash = hash_password(password)
        existing.is_active = True
        db_session.commit()
        db_session.refresh(existing)
        return existing
    user = User(email=email, password_hash=hash_password(password), role="admin", is_active=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def seed_paper(
    db_session: Session,
    *,
    arxiv_id: str = "1706.03762",
    title: str = "Attention Is All You Need",
    abstract: str = "Transformer architecture based on attention mechanisms.",
    primary_category: str = "cs.CL",
    ingest_status: str = "metadata_only",
) -> int:
    result = batch_upsert_papers(
        db_session,
        [
            PaperUpsert(
                arxiv_id=arxiv_id,
                title=title,
                authors=[AuthorInput(name="Author One")],
                abstract=abstract,
                primary_category=primary_category,
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                ingest_status=ingest_status,
            )
        ],
    )
    return result.items[0].paper_id


@pytest.fixture
def user_token(client: TestClient) -> str:
    return register_user(client)["access_token"]


@pytest.fixture
def user_headers(user_token: str) -> dict[str, str]:
    return auth_header(user_token)


@pytest.fixture
def admin_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    admin = seed_admin(db_session)
    from app.service.auth import login
    from app.schema.auth import LoginRequest

    auth = login(db_session, LoginRequest(email=admin.email, password="adminpass123"), client.app.state.settings)
    return auth_header(auth.access_token)
