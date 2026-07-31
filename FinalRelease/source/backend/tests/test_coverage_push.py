"""HTTP and service coverage for learning, admin, profile, subscriptions, papers, pdf_stream."""

from __future__ import annotations

import urllib.error

import pytest

from app.model import Paper, User
from app.schema.papers import SubscriptionSyncResult, UserActionInput, UserProfileUpdate
from app.service.auth import hash_password
from app.service.learning import create_action
from app.service.papers import PaperServiceError
from app.service.pdf_stream import ensure_paper_pdf_cached, load_paper_pdf_bytes
from app.service.profile import clear_dictionary, derive_topics_from_behavior, sync_topics_from_behavior, update_profile
from tests.conftest import seed_paper


@pytest.fixture(autouse=True)
def _noop_parse_job(monkeypatch):
    monkeypatch.setattr("app.api.papers.run_parse_agent_job", lambda *args, **kwargs: None)


def test_learning_actions_crud_and_errors(client, user_headers, db_session) -> None:
    user = client.get("/api/auth/me", headers=user_headers).json()["data"]
    user_id = user["user_id"]
    paper_id = seed_paper(db_session, arxiv_id="learn-crud", title="Learn CRUD")

    created = client.post(
        "/api/learning/actions",
        headers=user_headers,
        json={
            "user_id": user_id,
            "paper_id": paper_id,
            "action_type": "favorite",
            "payload_json": {"favorite": True},
        },
    )
    assert created.status_code == 200
    action_id = created.json()["data"]["id"]
    assert action_id

    listed = client.get(
        f"/api/learning/actions?user_id={user_id}&action_type=favorite",
        headers=user_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == action_id

    patched = client.patch(
        f"/api/learning/actions/{action_id}",
        headers=user_headers,
        json={"payload_json": {"favorite": False}},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["id"] == action_id

    bad_bulk = client.delete(
        f"/api/learning/actions/bulk?user_id={user_id}&action_type=not-a-real-type",
        headers=user_headers,
    )
    assert bad_bulk.status_code == 400

    missing = client.patch(
        "/api/learning/actions/99999",
        headers=user_headers,
        json={"payload_json": {}},
    )
    assert missing.status_code == 404

    deleted = client.delete(f"/api/learning/actions/{action_id}", headers=user_headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    create_action(
        db_session,
        UserActionInput(
            user_id=user_id,
            paper_id=paper_id,
            action_type="note",
            payload_json={"kind": "comment", "text": "Nice paper"},
        ),
    )
    comments = client.get(
        f"/api/learning/actions/public-comments?paper_id={paper_id}",
        headers=user_headers,
    )
    assert comments.status_code == 200
    assert comments.json()["data"][0]["id"]


def test_admin_user_and_pdf_routes(client, admin_headers, db_session) -> None:
    target = User(email="disable@example.com", password_hash=hash_password("pass"), role="user", is_active=True)
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    patched = client.patch(
        f"/api/admin/users/{target.id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "禁用"

    deleted = client.delete(f"/api/admin/users/{target.id}", headers=admin_headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    stats = client.get("/api/admin/pdfs/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert "papers" in stats.json()["data"]

    sync = client.post("/api/admin/pdfs/sync?limit=1&delay_s=0", headers=admin_headers)
    assert sync.status_code == 200
    assert "requested" in sync.json()["data"]


def test_profile_api_and_dictionary(client, user_headers, db_session) -> None:
    user = client.get("/api/auth/me", headers=user_headers).json()["data"]
    user_id = user["user_id"]

    profile_get = client.get(f"/api/learning/profile?user_id={user_id}", headers=user_headers)
    assert profile_get.status_code == 200
    assert profile_get.json()["data"]["user_id"] == user_id

    profile_put = client.put(
        f"/api/learning/profile?user_id={user_id}",
        headers=user_headers,
        json={"persona": "研究", "topics": ["cs.CL"], "preferences": {}},
    )
    assert profile_put.status_code == 200
    assert profile_put.json()["data"]["topics"] == ["cs.CL"]

    dictionary = client.get(f"/api/learning/dictionary?user_id={user_id}", headers=user_headers)
    assert dictionary.status_code == 200
    assert isinstance(dictionary.json()["data"], list)


def test_subscriptions_sync_route(client, user_headers, monkeypatch) -> None:
    user = client.get("/api/auth/me", headers=user_headers).json()["data"]
    user_id = user["user_id"]

    saved = client.put(
        f"/api/subscriptions?user_id={user_id}",
        headers=user_headers,
        json={"subscriptions": [{"key": "s1", "type": "keyword", "value": "Transformer", "enabled": True}]},
    )
    assert saved.status_code == 200

    fake = SubscriptionSyncResult(user_id=user_id, fetched=2, created=1, updated=1)
    monkeypatch.setattr("app.api.subscriptions.sync_subscriptions", lambda *args, **kwargs: fake)

    synced = client.post(f"/api/subscriptions/sync?user_id={user_id}", headers=user_headers)
    assert synced.status_code == 200
    data = synced.json()["data"]
    assert data["user_id"] == user_id
    assert data["fetched"] == 2
    assert data["created"] == 1
    assert data["updated"] == 1


def test_papers_smart_search_and_priority(client, user_headers, db_session, monkeypatch) -> None:
    paper_id = seed_paper(db_session, arxiv_id="smart-pri", title="Smart Priority Paper")

    from app.schema.papers import SmartSearchResponse

    fake_search = SmartSearchResponse(
        query="attention",
        rewritten_query="attention",
        keywords=["attention"],
        intent="find papers",
        search_session_id="sess-mock-1",
        answer="found",
        plan_source="heuristic",
        answer_source="template",
        items=[],
        total=0,
        page=1,
        page_size=12,
        pages=0,
    )
    monkeypatch.setattr("app.api.papers.smart_search_papers", lambda *args, **kwargs: fake_search)

    search = client.post(
        "/api/papers/smart-search",
        headers=user_headers,
        json={"query": "attention transformer", "page": 1, "page_size": 12},
    )
    assert search.status_code == 200
    assert search.json()["data"]["search_session_id"] == "sess-mock-1"

    priority = client.post(f"/api/papers/{paper_id}/parse/priority", headers=user_headers)
    assert priority.status_code == 200
    assert priority.json()["data"]["paper_id"] == paper_id


def test_pdf_stream_download_and_errors(db_session, settings, monkeypatch) -> None:
    paper_id = seed_paper(db_session, arxiv_id="pdf-dl", title="PDF Download")
    paper = db_session.get(Paper, paper_id)
    assert paper is not None
    assert paper.arxiv_id == "pdf-dl"

    monkeypatch.setattr("app.service.pdf_stream._resolve_pdf_url", lambda _paper: None)
    with pytest.raises(PaperServiceError) as exc:
        ensure_paper_pdf_cached(db_session, paper_id, settings=settings, force=True)
    assert exc.value.code == "PDF_NOT_FOUND"
    assert db_session.get(Paper, paper_id).arxiv_id == "pdf-dl"

    monkeypatch.setattr(
        "app.service.pdf_stream._resolve_pdf_url",
        lambda p: f"https://arxiv.org/pdf/{p.arxiv_id}.pdf",
    )
    pdf_bytes = b"%PDF-1.4 downloaded"

    class FakeResp:
        def read(self, n=-1):
            return pdf_bytes

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=60: FakeResp())
    path = ensure_paper_pdf_cached(db_session, paper_id, settings=settings, force=True)
    assert path.is_file()
    data, ctype = load_paper_pdf_bytes(db_session, paper_id, settings=settings)
    assert data.startswith(b"%PDF")
    assert ctype == "application/pdf"

    def boom(req, timeout=60):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(PaperServiceError) as fetch_exc:
        ensure_paper_pdf_cached(db_session, paper_id, settings=settings, force=True)
    assert fetch_exc.value.code == "PDF_FETCH_FAILED"


def test_profile_service_extended(db_session) -> None:
    update_profile(
        db_session,
        "ext-user",
        UserProfileUpdate(preferences={"auto_topics_enabled": False}),
    )
    assert derive_topics_from_behavior(db_session, "ext-user") == []

    paper_id = seed_paper(db_session, arxiv_id="ext-prof", title="Ext Prof", primary_category="cs.SE")
    create_action(
        db_session,
        UserActionInput(
            user_id="ext-user",
            paper_id=paper_id,
            action_type="favorite",
            payload_json={"favorite": True},
        ),
    )

    paused = sync_topics_from_behavior(db_session, "ext-user")
    assert paused is not None
    assert paused.topics == []

    update_profile(
        db_session,
        "ext-user",
        UserProfileUpdate(preferences={"auto_topics_enabled": True}),
    )
    synced = sync_topics_from_behavior(db_session, "ext-user")
    assert synced is not None
    assert "cs.SE" in synced.topics

    cleared = clear_dictionary(db_session, "ext-user")
    assert cleared["cleared"] >= 0
    assert cleared["hidden_total"] >= 0


def test_search_session_route(client, user_headers, db_session) -> None:
    seed_paper(db_session, arxiv_id="sess-a", title="Session Paper One about attention")
    seed_paper(db_session, arxiv_id="sess-b", title="Session Paper Two about attention")

    first = client.post(
        "/api/papers/smart-search",
        headers=user_headers,
        json={"query": "attention", "page": 1, "page_size": 1, "include_answer": False},
    )
    assert first.status_code == 200
    session_id = first.json()["data"]["search_session_id"]
    assert session_id

    first_total = first.json()["data"]["total"]
    second = client.post(
        "/api/papers/smart-search",
        headers=user_headers,
        json={
            "query": "attention",
            "page": 2,
            "page_size": 1,
            "search_session_id": session_id,
            "include_answer": False,
        },
    )
    assert second.status_code == 200
    assert second.json()["data"]["search_session_id"] == session_id
    assert second.json()["data"]["total"] == first_total
    assert second.json()["data"]["answer_source"] == "skipped"
