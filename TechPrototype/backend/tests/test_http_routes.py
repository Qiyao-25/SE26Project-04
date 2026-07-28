"""Comprehensive FastAPI TestClient route coverage."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.repository.chunks import upsert_chunks
from app.schema.papers import StructuredResultBatch, StructuredResultInput, TaskUpdate, TextChunkBatch, TextChunkInput
from app.service.tasks import create_task, save_results, update_task
from tests.conftest import auth_header, register_user, seed_admin, seed_paper


@pytest.fixture(autouse=True)
def _noop_parse_job(monkeypatch):
    monkeypatch.setattr("app.api.papers.run_parse_agent_job", lambda *args, **kwargs: None)


def test_health_ok_and_degraded(client, monkeypatch):
    from app.schema.common import HealthData

    ok = client.get("/health")
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "ok"
    assert ok.headers.get("X-Request-ID")

    monkeypatch.setattr(
        "app.api.health.get_health",
        lambda engine, settings: HealthData(
            status="degraded",
            database="unavailable",
            environment="test",
            version="0.1.0",
            component_versions={"api": "0.1.0"},
        ),
    )
    bad = client.get("/health")
    assert bad.status_code == 503
    assert client.get("/api/health").status_code == 503


def test_auth_routes(client):
    assert client.get("/api/auth/me").status_code == 401
    dup = client.post("/api/auth/register", json={"email": "bad-email", "password": "password123"})
    assert dup.status_code == 400

    auth = register_user(client, email="routes@example.com")
    headers = auth_header(auth["access_token"])
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "routes@example.com"

    login = client.post("/api/auth/login", json={"email": "routes@example.com", "password": "password123"})
    assert login.status_code == 200
    bad_login = client.post("/api/auth/login", json={"email": "routes@example.com", "password": "wrong123"})
    assert bad_login.status_code == 401

    updated = client.put(
        "/api/auth/account",
        headers=headers,
        json={"email": "routes-renamed@example.com", "current_password": "password123", "password": "newpassword123"},
    )
    assert updated.status_code == 200


def test_papers_list_detail_batch_chunks_search(client, admin_headers, user_headers, db_session):
    paper_id = seed_paper(db_session, arxiv_id="route-paper", title="Route Paper")
    listed = client.get("/api/papers")
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] >= 1

    detail = client.get(f"/api/papers/{paper_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["paper_id"] == paper_id

    batch = client.post(
        "/api/papers/batch",
        headers=admin_headers,
        json=[{"arxiv_id": "batch-new", "title": "Batch New"}],
    )
    assert batch.status_code == 200

    upsert_chunks(
        db_session,
        paper_id,
        TextChunkBatch(chunks=[TextChunkInput(chunk_id="c1", page_no=1, section="intro", content="attention model text")]),
    )
    chunks = client.post("/api/search/chunks", headers=user_headers, json={"query": "attention", "paper_id": paper_id, "top_k": 5})
    assert chunks.status_code == 200
    assert isinstance(chunks.json()["data"]["chunks"], list)

    admin_chunks = client.post(
        f"/api/papers/{paper_id}/chunks",
        headers=admin_headers,
        json={"chunks": [{"chunk_id": "c2", "page_no": 2, "section": "method", "content": "method details"}]},
    )
    assert admin_chunks.status_code == 200


def test_tasks_routes(client, admin_headers, user_headers, db_session):
    paper_id = seed_paper(db_session, arxiv_id="task-route", title="Task Route")
    created = client.post(
        f"/api/papers/{paper_id}/parse",
        headers={**user_headers, "Idempotency-Key": "route-parse-key"},
        json={"task_type": "full_parse", "force": False},
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["task_id"]

    detail = client.get(f"/api/tasks/{task_id}", headers=user_headers)
    assert detail.status_code == 200

    listed = client.get("/api/tasks", headers=admin_headers)
    assert listed.status_code == 200

    stats = client.get("/api/tasks/stats", headers=admin_headers)
    assert stats.status_code == 200

    enqueue = client.post("/api/tasks/enqueue-pending", headers=admin_headers)
    assert enqueue.status_code == 200


def test_learning_profile_subscriptions_recommendations(client, user_headers, db_session):
    user = client.get("/api/auth/me", headers=user_headers).json()["data"]
    user_id = user["user_id"]

    profile_get = client.get(f"/api/learning/profile?user_id={user_id}", headers=user_headers)
    assert profile_get.status_code == 200
    profile_put = client.put(
        f"/api/learning/profile?user_id={user_id}",
        headers=user_headers,
        json={"persona": "研究", "topics": ["cs.CL"], "preferences": {}},
    )
    assert profile_put.status_code == 200

    dictionary = client.get(f"/api/learning/dictionary?user_id={user_id}", headers=user_headers)
    assert dictionary.status_code == 200

    subs = client.put(
        f"/api/subscriptions?user_id={user_id}",
        headers=user_headers,
        json={"subscriptions": [{"key": "sub-1", "type": "keyword", "value": "Transformer", "enabled": True}]},
    )
    assert subs.status_code == 200
    subs_get = client.get(f"/api/subscriptions?user_id={user_id}", headers=user_headers)
    assert subs_get.status_code == 200

    daily = client.get("/api/recommendations/daily")
    assert daily.status_code == 200
    profile_rec = client.get(f"/api/recommendations/profile?user_id={user_id}", headers=user_headers)
    assert profile_rec.status_code == 200
    sub_rec = client.get(f"/api/recommendations/subscriptions?user_id={user_id}", headers=user_headers)
    assert sub_rec.status_code == 200


def test_admin_routes(client, admin_headers, db_session):
    seed_paper(db_session, arxiv_id="admin-route", title="Admin Route")
    assert client.get("/api/admin/overview", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/tasks", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/users", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/quality", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/audit", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/crawl-settings", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/pdfs/stats", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/overview", headers={"Authorization": "Bearer invalid"}).status_code in {401, 403}


def test_papers_extended_routes(client, user_headers, db_session, monkeypatch):
    paper_id = seed_paper(db_session, arxiv_id="extended-paper", title="Extended Paper", ingest_status="qa_ready")
    task, _ = create_task(db_session, paper_id, "full_parse", "extended-task")
    save_results(
        db_session,
        task.task_id,
        StructuredResultBatch(
            results=[
                StructuredResultInput(result_type="summary", content_json={"summary": "A transformer survey."}),
            ]
        ),
    )
    upsert_chunks(
        db_session,
        paper_id,
        TextChunkBatch(chunks=[TextChunkInput(chunk_id="qa-chunk", page_no=1, content="The attention model is described here.")]),
    )

    assert client.get(f"/api/papers/{paper_id}/wiki").status_code == 200
    assert client.get(f"/api/papers/{paper_id}/summary").status_code == 200
    assert client.get(f"/api/papers/{paper_id}/content").status_code == 200
    assert client.get(f"/api/papers/{paper_id}/chunks", headers=user_headers).status_code == 200
    assert client.get(f"/api/papers/{paper_id}/assist", headers=user_headers).status_code == 200
    assert client.get(f"/api/papers/{paper_id}/graph", headers=user_headers).status_code == 200
    assert client.post(f"/api/papers/{paper_id}/graph", headers=user_headers).status_code == 200
    assert client.post(f"/api/papers/{paper_id}/assist", headers=user_headers, json={"mode": "研究", "force": False}).status_code == 200

    other_id = seed_paper(db_session, arxiv_id="extended-other", title="Other Paper")
    compare = client.post(f"/api/papers/{paper_id}/compare", headers=user_headers, json={"other_paper_id": other_id})
    assert compare.status_code == 200

    from datetime import datetime, timezone

    from app.schema.papers import QaResponse

    def fake_answer(db, pid, question, **kwargs):
        return QaResponse(
            conversation_id="conv-1",
            message_id="msg-1",
            paper_id=pid,
            answer="The paper discusses attention.",
            created_at=datetime.now(timezone.utc),
            citations=[
                {
                    "citationId": f"citation-{pid}-qa-chunk",
                    "paperId": pid,
                    "paperTitle": "Extended Paper",
                    "sectionId": "qa-chunk",
                    "sectionTitle": "intro",
                    "pageNumber": 1,
                    "quote": "The attention model is described here.",
                }
            ],
            answer_mode="agent",
        )

    monkeypatch.setattr("app.api.papers.answer_question", fake_answer)
    qa = client.post(
        f"/api/papers/{paper_id}/qa",
        headers=user_headers,
        json={"question": "What is the method?", "history": [], "conversationId": None, "scope": "both"},
    )
    assert qa.status_code == 200
    assert qa.json()["data"]["answer"]


def test_fetch_one_route_mock(client, user_headers, monkeypatch):
    from app.service.arxiv_client import ArxivPaperMeta

    meta = ArxivPaperMeta(
        arxiv_id="2401.88888",
        title="Fetched Via Route",
        authors=["Bob"],
        abstract="abs",
        categories=["cs.CL"],
        pdf_url="https://arxiv.org/pdf/2401.88888.pdf",
        abs_url="https://arxiv.org/abs/2401.88888",
        published="2024-01-01T00:00:00Z",
    )

    class FakeClient:
        def resolve_query(self, *args, **kwargs):
            return [meta]

    monkeypatch.setattr("app.service.arxiv_client.ArxivClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr("app.service.pdf_stream.ensure_paper_pdf_cached", lambda *args, **kwargs: None)
    response = client.post("/api/papers/fetch-one", headers=user_headers, json={"query": "2401.88888", "parse": False})
    assert response.status_code == 200


def test_task_worker_routes(client, admin_headers, db_session):
    paper_id = seed_paper(db_session, arxiv_id="worker-paper", title="Worker Paper")
    task, _ = create_task(db_session, paper_id, "full_parse", "worker-task")
    worker = {"X-Worker-Token": client.app.state.settings.worker_token}

    claim = client.post("/api/tasks/claim", headers=worker, json={"worker_id": "route-worker"})
    assert claim.status_code == 200
    claimed = claim.json()["data"]
    assert claimed is not None
    lease = claimed["lease_token"]

    patch = client.patch(
        f"/api/tasks/{task.task_id}",
        headers={**worker, "X-Task-Lease": lease},
        json={"status": "running", "stage": "parse"},
    )
    assert patch.status_code == 200

    results = client.post(
        f"/api/tasks/{task.task_id}/results",
        headers={**worker, "X-Task-Lease": lease},
        json={"results": [{"result_type": "summary", "content_json": {"summary": "done"}, "source_locator": {}}]},
    )
    assert results.status_code == 200

    recover = client.post("/api/tasks/recover-stale", headers=admin_headers)
    assert recover.status_code == 200
