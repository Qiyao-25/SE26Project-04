"""Final coverage push toward 90%."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, Paper
from app.schema.papers import PaperUpsert
from app.service import parse_agent_runner
from app.service.papers import PaperServiceError, batch_upsert_papers, delete_paper
from app.service.parse_agent_runner import run_parse_agent_job
from app.service.pdf_stream import (
    cache_paper_ids,
    ensure_paper_pdf_cached,
    resolve_storage_dir,
    sync_missing_paper_pdfs,
)
from app.service.tasks import claim_task, create_task
from tests.conftest import auth_header, register_user, seed_admin, seed_paper

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 0\ntrailer\n<<>>\nstartxref\n0\n%%EOF"


def test_admin_api_error_branches(client, admin_headers, db_session):
    assert client.patch("/api/admin/users/99999", headers=admin_headers, json={"is_active": False}).status_code == 404
    assert client.delete("/api/admin/users/99999", headers=admin_headers).status_code == 404

    admin = seed_admin(db_session, email="protected-admin@example.com")
    assert (
        client.patch(f"/api/admin/users/{admin.id}", headers=admin_headers, json={"is_active": False}).status_code
        == 400
    )
    assert client.delete(f"/api/admin/users/{admin.id}", headers=admin_headers).status_code == 400

    crawl = client.patch(
        "/api/admin/crawl-settings",
        headers=admin_headers,
        json={"crawl_enabled": True, "crawl_interval_s": 300},
    )
    assert crawl.status_code == 200


def test_learning_internal_error(client, user_headers, monkeypatch):
    monkeypatch.setattr(
        "app.api.learning.create_action",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("UNKNOWN")),
    )
    user = client.get("/api/auth/me", headers=user_headers).json()["data"]
    resp = client.post(
        "/api/learning/actions",
        headers=user_headers,
        json={"user_id": user["user_id"], "paper_id": 1, "action_type": "favorite", "payload_json": {}},
    )
    assert resp.status_code == 500


def test_profile_dictionary_clear(client, user_headers):
    user = client.get("/api/auth/me", headers=user_headers).json()["data"]
    user_id = user["user_id"]
    cleared = client.delete(f"/api/learning/dictionary?user_id={user_id}", headers=user_headers)
    assert cleared.status_code == 200


def test_papers_admin_delete(client, admin_headers, db_session):
    paper_id = seed_paper(db_session, arxiv_id="admin-del", title="Admin Delete")
    resp = client.delete(f"/api/papers/{paper_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["paper_id"] == paper_id


def test_parse_agent_job_worker_crash(tmp_path, monkeypatch):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'crash.db'}",
        parse_agent_enabled=True,
        llm_api_key="k",
        llm_model="m",
    )
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="crash-p", title="Crash")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "crash-task")

    def boom(*args, **kwargs):
        raise RuntimeError("worker exploded")

    monkeypatch.setattr(parse_agent_runner, "_execute", boom)
    run_parse_agent_job(engine, task.task_id, settings)
    with Session(engine) as session:
        from app.model import ParseTask

        saved = session.get(ParseTask, task.task_id)
        assert saved is not None
        assert saved.error_code == "WORKER_ERROR"


def test_execute_persist_and_summarize_crash(tmp_path, monkeypatch):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'exec.db'}",
        parse_agent_enabled=True,
        llm_api_key="k",
        llm_model="m",
    )
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    body = "[page 1] Attention model with sufficient text for parsing pipeline to proceed."

    with Session(engine) as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="exec-p", title="Exec", abstract="abs")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "exec-task")
        claimed = claim_task(session, "worker-x")
        assert claimed and claimed.lease_token

        monkeypatch.setattr(
            parse_agent_runner,
            "_extract_paper_text",
            lambda paper, settings: (body, 1, "pdf", "/tmp/fake.pdf"),
        )
        monkeypatch.setattr(parse_agent_runner, "_persist_paper_content", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("persist fail")))

        class CrashSummarize:
            def run(self, **kwargs):
                raise RuntimeError("summarize crash")

        from app.agents.graph_agent import PaperGraph

        monkeypatch.setattr(parse_agent_runner, "SummarizeAgent", lambda s: CrashSummarize())
        monkeypatch.setattr(
            parse_agent_runner,
            "GraphAgent",
            lambda s: MagicMock(run=lambda **k: PaperGraph(nodes=[], edges=[], lineage=[], narrative="", source="test")),
        )
        monkeypatch.setattr(parse_agent_runner, "ContentValidationAgent", lambda: MagicMock(validate_wiki=lambda **k: MagicMock(flags=[])))

        from app.service.parse_agent_runner import _execute

        _execute(session, task.task_id, settings, lease_token=claimed.lease_token)
        saved = session.get(Paper, paper_id)
        assert saved is not None
        assert saved.ingest_status == "qa_ready"


def test_smart_search_legacy_reuse_and_pdf_local_path(db_session, settings, tmp_path):
    from app.service.papers import smart_search_papers
    from app.service.pdf_stream import local_pdf_path

    for i in range(3):
        seed_paper(db_session, arxiv_id=f"legacy-{i}", title=f"Legacy Search Paper {i}", primary_category="cs.CL")

    legacy = smart_search_papers(
        db_session,
        query="Legacy Search",
        page=1,
        page_size=2,
        rewritten_query="Legacy Search",
        keywords=["Legacy", "Search"],
        author_hints=[],
        category_hints=["cs.CL"],
        search_mode="topic",
        include_answer=False,
        settings=settings,
    )
    assert legacy.total >= 1
    assert legacy.plan_source == "reused"

    paper_id = seed_paper(db_session, arxiv_id="local-pdf", title="Local PDF")
    paper = db_session.get(Paper, paper_id)
    assert paper is not None
    cache_dir = tmp_path / "pdfs"
    cache_dir.mkdir(parents=True)
    cache_file = cache_dir / "local-pdf.pdf"
    cache_file.write_bytes(PDF_BYTES)
    settings.paper_storage_dir = str(cache_dir)
    found = local_pdf_path(db_session, paper, settings)
    assert found == cache_file


def test_tasks_recover_and_auth_errors(client, admin_headers, monkeypatch):
    monkeypatch.setattr("app.api.papers.run_parse_agent_job", lambda *args, **kwargs: None)
    recover = client.post("/api/tasks/recover-stale", headers=admin_headers)
    assert recover.status_code == 200

    assert client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "password123"}).status_code == 401
    assert client.post("/api/auth/register", json={"email": "bad", "password": "short"}).status_code == 400


def test_learning_delete_forbidden(client, db_session):
    auth_a = register_user(client, email="owner@example.com")
    auth_b = register_user(client, email="intruder@example.com")
    paper_id = seed_paper(db_session, arxiv_id="forbid-del", title="Forbid Del")
    created = client.post(
        "/api/learning/actions",
        headers=auth_header(auth_a["access_token"]),
        json={
            "user_id": auth_a["user"]["user_id"],
            "paper_id": paper_id,
            "action_type": "favorite",
            "payload_json": {"favorite": True},
        },
    )
    action_id = created.json()["data"]["id"]
    forbidden = client.delete(
        f"/api/learning/actions/{action_id}",
        headers=auth_header(auth_b["access_token"]),
    )
    assert forbidden.status_code == 403


def test_learning_public_comments_missing_paper(client, user_headers):
    missing = client.get("/api/learning/actions/public-comments?paper_id=99999", headers=user_headers)
    assert missing.status_code == 404


def test_learning_list_invalid_action_type(client, user_headers):
    user = client.get("/api/auth/me", headers=user_headers).json()["data"]
    bad = client.get(
        f"/api/learning/actions?user_id={user['user_id']}&action_type=not-valid",
        headers=user_headers,
    )
    assert bad.status_code == 400


def test_topic_from_category_and_validate_action(db_session):
    from app.schema.papers import UserActionInput
    from app.service.learning import validate_action
    from app.service.papers import topic_from_category

    assert topic_from_category("cs.CL") == "cs"
    assert topic_from_category("physics") == "physics"
    assert topic_from_category(None) is None

    with pytest.raises(ValueError, match="VALIDATION_ERROR"):
        validate_action(
            db_session,
            UserActionInput(user_id="u", paper_id=1, action_type="invalid", payload_json={}),
        )


def test_learning_comments_filter_and_history_dedupe(db_session, monkeypatch):
    from app.schema.papers import UserActionInput
    from app.service.learning import create_action, list_actions, list_public_comments

    paper_id = seed_paper(db_session, arxiv_id="learn-extra", title="Learn Extra")
    other_id = seed_paper(db_session, arxiv_id="learn-extra-2", title="Learn Extra 2")

    create_action(
        db_session,
        UserActionInput(
            user_id="learn-u",
            paper_id=paper_id,
            action_type="note",
            payload_json={"kind": "comment", "text": "Nice work"},
        ),
    )
    create_action(
        db_session,
        UserActionInput(user_id="learn-u", paper_id=paper_id, action_type="reading_history", payload_json={}),
    )
    create_action(
        db_session,
        UserActionInput(user_id="learn-u", paper_id=paper_id, action_type="reading_history", payload_json={}),
    )
    create_action(
        db_session,
        UserActionInput(user_id="learn-u", paper_id=other_id, action_type="reading_history", payload_json={}),
    )

    comments = list_public_comments(db_session, paper_id, limit=5)
    assert len(comments) == 1

    history = list_actions(db_session, "learn-u", None, "reading_history")
    assert len(history) == 2

    monkeypatch.setattr(
        "app.service.profile.sync_topics_from_behavior",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sync fail")),
    )
    create_action(
        db_session,
        UserActionInput(user_id="learn-u", paper_id=other_id, action_type="favorite", payload_json={"favorite": True}),
    )


def test_pdf_stream_extended(tmp_path, monkeypatch):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'pdf-ext.db'}",
        paper_storage_dir="data/pdfs",
    )
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)

    storage = resolve_storage_dir(settings)
    assert storage.is_dir()

    with Session(engine) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="pdf-ext", title="PDF Ext", pdf_url="https://arxiv.org/pdf/pdf-ext.pdf")],
        ).items[0].paper_id

        class FakeResp:
            def read(self, n=-1):
                return PDF_BYTES

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResp())
        sync = sync_missing_paper_pdfs(session, limit=3, delay_s=0, settings=settings)
        assert "requested" in sync

        result = cache_paper_ids(session, [paper_id], settings=settings, delay_s=0)
        assert result["requested"] == 1

        class HugeResp:
            def read(self, n=-1):
                return b"x" * (41 * 1024 * 1024)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: HugeResp())
        with pytest.raises(PaperServiceError) as too_large:
            ensure_paper_pdf_cached(session, paper_id, settings=settings, force=True)
        assert too_large.value.code == "PDF_TOO_LARGE"


def test_papers_service_compare_same(client, db_session):
    left = seed_paper(db_session, arxiv_id="same-a", title="Same")
    with pytest.raises(PaperServiceError) as exc:
        from app.service.papers import compare_papers

        compare_papers(db_session, paper_id=left, other_paper_id=left)
    assert exc.value.code == "COMPARE_SAME_PAPER"
    delete_paper(db_session, left)


def test_auth_account_success(client):
    auth = register_user(client, email="acct@example.com", password="password123")
    headers = auth_header(auth["access_token"])
    updated = client.put(
        "/api/auth/account",
        headers=headers,
        json={"email": "acct-renamed@example.com", "current_password": "password123", "password": "newpassword123"},
    )
    assert updated.status_code == 200


def test_execute_graph_validation_related_fallbacks(tmp_path, monkeypatch):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'fb.db'}",
        parse_agent_enabled=True,
        llm_api_key="k",
        llm_model="m",
    )
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    body = "[page 1] Attention model with sufficient text for parsing pipeline to proceed."

    with Session(engine) as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="fb-p", title="Fallbacks", abstract="abs")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "fb-task")
        claimed = claim_task(session, "worker-fb")
        assert claimed and claimed.lease_token

        monkeypatch.setattr(
            parse_agent_runner,
            "_extract_paper_text",
            lambda paper, settings: (body, 1, "pdf", None),
        )

        class OkSummarize:
            def run(self, **kwargs):
                from app.agents.summarize_agent import build_fallback_summary

                return build_fallback_summary(
                    title=kwargs.get("title", ""),
                    abstract=kwargs.get("abstract", ""),
                    body_text=kwargs.get("body_text", ""),
                    arxiv_id=kwargs.get("arxiv_id", ""),
                )

        class BoomGraph:
            def run(self, **kwargs):
                raise RuntimeError("graph down")

        class BoomValidate:
            def validate_wiki(self, **kwargs):
                raise RuntimeError("validate down")

        monkeypatch.setattr(parse_agent_runner, "SummarizeAgent", lambda s: OkSummarize())
        monkeypatch.setattr(parse_agent_runner, "GraphAgent", lambda s: BoomGraph())
        monkeypatch.setattr(parse_agent_runner, "ContentValidationAgent", lambda: BoomValidate())
        monkeypatch.setattr(
            parse_agent_runner,
            "get_related_paper_payloads",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("related fail")),
        )

        from app.service.parse_agent_runner import _execute

        _execute(session, task.task_id, settings, lease_token=claimed.lease_token)
        saved = session.get(Paper, paper_id)
        assert saved is not None
        assert saved.ingest_status == "qa_ready"
