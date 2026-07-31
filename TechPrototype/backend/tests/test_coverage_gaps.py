"""Miscellaneous coverage gap tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.agents.llm_client import LlmError
from app.core.config import Settings
from app.schema.papers import PaperUpsert, StructuredResultBatch, StructuredResultInput, TaskUpdate, TextChunkBatch, TextChunkInput, UserActionInput
from app.service.arxiv_client import _parse_atom_feed
from app.service.learning import create_action
from app.service.papers import PaperServiceError, batch_upsert_papers, fetch_one_paper
from app.service.tasks import create_task, update_task
from tests.conftest import auth_header, register_user, seed_paper


SAMPLE_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <title>Atom Paper</title>
    <summary>Abstract.</summary>
    <author><name>Alice</name></author>
  </entry>
</feed>
"""


def test_extract_arxiv_pdf_url_from_atom_feed() -> None:
    papers = _parse_atom_feed(SAMPLE_ATOM)
    assert papers[0].pdf_url.endswith("2401.01234.pdf")


def test_learning_sync_failure_is_swallowed(db_session, monkeypatch) -> None:
    paper_id = seed_paper(db_session, arxiv_id="sync-fail", title="Sync Fail")
    monkeypatch.setattr(
        "app.service.profile.sync_topics_from_behavior",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("profile sync failed")),
    )
    item, created = create_action(
        db_session,
        UserActionInput(user_id="sync-user", paper_id=paper_id, action_type="favorite", payload_json={"favorite": True}),
    )
    assert created is True
    assert item.paper_id == paper_id


def test_task_worker_routes_return_404(client, admin_headers):
    worker = {"X-Worker-Token": client.app.state.settings.worker_token}
    missing = client.post(
        "/api/tasks/99999/finalize",
        headers=worker,
        json={
            "chunks": [{"chunk_id": "c1", "content": "evidence text"}],
            "results": [{"result_type": "summary", "content_json": {"summary": "ok"}}],
        },
    )
    assert missing.status_code == 404
    retry_missing = client.post("/api/tasks/99999/retry", headers=admin_headers)
    assert retry_missing.status_code == 404


def test_learning_public_comments_route(client, db_session) -> None:
    paper_id = seed_paper(db_session, arxiv_id="comments-paper", title="Comments Paper")
    auth = register_user(client, email="commenter@example.com")
    user_id = auth["user"]["user_id"]
    headers = auth_header(auth["access_token"])
    create_action(
        db_session,
        UserActionInput(
            user_id=user_id,
            paper_id=paper_id,
            action_type="note",
            payload_json={"kind": "comment", "text": "Great paper"},
        ),
    )
    response = client.get(f"/api/learning/actions/public-comments?paper_id={paper_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)


def test_fetch_one_arxiv_error(monkeypatch, db_session) -> None:
    class BrokenClient:
        def resolve_query(self, *args, **kwargs):
            raise RuntimeError("network")

    monkeypatch.setattr("app.service.arxiv_client.ArxivClient", lambda **kwargs: BrokenClient())
    with pytest.raises(PaperServiceError) as exc:
        fetch_one_paper(db_session, query="2401.01234", parse=False, settings=Settings(environment="test", database_url="sqlite:///:memory:"))
    assert exc.value.code == "ARXIV_FETCH_FAILED"
