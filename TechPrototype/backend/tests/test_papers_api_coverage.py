"""HTTP coverage for papers API error paths."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.agents.llm_client import LlmError
from app.schema.papers import PaperUpsert, StructuredResultBatch, StructuredResultInput, TaskUpdate, TextChunkBatch, TextChunkInput
from app.service.arxiv_client import ArxivPaperMeta
from app.service.papers import PaperServiceError
from app.service.tasks import create_task, save_results, update_task
from tests.conftest import auth_header, register_user, seed_paper


def test_batch_validation_error(client, user_headers) -> None:
    response = client.post("/api/papers/batch", headers=user_headers, json={"papers": []})
    assert response.status_code == 403


def test_parse_requires_idempotency_key(client, user_headers, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.papers.run_parse_agent_job", lambda *args, **kwargs: None)
    paper_id = seed_paper(db_session)
    response = client.post(f"/api/papers/{paper_id}/parse", headers=user_headers, json={"task_type": "full_parse", "force": False})
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_parse_unknown_paper(client, user_headers, monkeypatch) -> None:
    monkeypatch.setattr("app.api.papers.run_parse_agent_job", lambda *args, **kwargs: None)
    response = client.post(
        "/api/papers/99999/parse",
        headers={**user_headers, "Idempotency-Key": "missing-paper"},
        json={"task_type": "full_parse", "force": False},
    )
    assert response.status_code == 404


def test_compare_llm_error(client, user_headers, db_session, monkeypatch) -> None:
    left = seed_paper(db_session, arxiv_id="cmp-a", title="Paper A")
    right = seed_paper(db_session, arxiv_id="cmp-b", title="Paper B")

    class BrokenCompare:
        def compare(self, **kwargs):
            raise LlmError("compare failed")

    monkeypatch.setattr("app.agents.compare_agent.CompareAgent", lambda settings: BrokenCompare())
    response = client.post(
        f"/api/papers/{left}/compare",
        headers=user_headers,
        json={"other_paper_id": right},
    )
    assert response.status_code == 502
    assert response.json()["code"] == "LLM_ERROR"


def test_pdf_route_uses_mock(client, user_headers, db_session, monkeypatch) -> None:
    paper_id = seed_paper(db_session, arxiv_id="pdf-mock", title="PDF Mock")
    monkeypatch.setattr(
        "app.api.papers.load_paper_pdf_bytes",
        lambda session, paper_id, settings=None: (b"%PDF-1.4 test", "application/pdf"),
    )
    response = client.get(f"/api/papers/{paper_id}/pdf", headers=user_headers)
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_chunks_and_wiki_404(client, user_headers) -> None:
    assert client.get("/api/papers/99999/wiki").status_code == 404
    assert client.get("/api/papers/99999/chunks", headers=user_headers).status_code == 404


def test_fetch_one_error(client, user_headers, monkeypatch) -> None:
    class EmptyClient:
        def resolve_query(self, *args, **kwargs):
            return []

    monkeypatch.setattr("app.api.papers.run_parse_agent_job", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.service.arxiv_client.ArxivClient", lambda **kwargs: EmptyClient())
    response = client.post("/api/papers/fetch-one", headers=user_headers, json={"query": "missing title", "parse": False})
    assert response.status_code == 404
    assert response.json()["code"] == "PAPER_NOT_FOUND"


def test_fetch_one_success_mock(client, user_headers, monkeypatch) -> None:
    meta = ArxivPaperMeta(
        arxiv_id="2401.99999",
        title="Fetched Paper",
        authors=["Alice"],
        abstract="abs",
        categories=["cs.CL"],
        pdf_url="https://arxiv.org/pdf/2401.99999.pdf",
        abs_url="https://arxiv.org/abs/2401.99999",
        published="2024-01-01T00:00:00Z",
    )

    class FakeClient:
        def resolve_query(self, *args, **kwargs):
            return [meta]

    monkeypatch.setattr("app.api.papers.run_parse_agent_job", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.service.arxiv_client.ArxivClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr("app.service.pdf_stream.ensure_paper_pdf_cached", lambda *args, **kwargs: None)
    response = client.post("/api/papers/fetch-one", headers=user_headers, json={"query": "2401.99999", "parse": True})
    assert response.status_code == 200
    assert response.json()["data"]["item"]["arxiv_id"] == "2401.99999"
