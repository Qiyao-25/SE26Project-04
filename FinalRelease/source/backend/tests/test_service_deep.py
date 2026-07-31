"""Deep service-layer branch coverage for learning, papers, tasks, recommendations, arxiv, auth."""

from __future__ import annotations

import urllib.error
from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.schema.papers import (
    AuthorInput,
    PaperUpsert,
    StructuredResultBatch,
    StructuredResultInput,
    TaskUpdate,
    UserActionInput,
    UserActionUpdate,
)
from app.service.arxiv_client import ArxivClient, _parse_atom_feed
from app.service.learning import (
    create_action,
    delete_action,
    delete_actions_by_type,
    list_actions,
    list_public_comments,
    update_action,
)
from app.service.papers import (
    PaperServiceError,
    compare_papers,
    get_reading_assist,
    get_wiki,
    search_papers,
    smart_search_papers,
)
from app.service.recommendations import daily_picks, profile_recommendations, subscription_recommendations
from app.service.search_query_normalize import (
    expand_chinese_topics,
    extract_author_candidates,
    infer_search_mode,
    paper_matches_excludes,
)
from app.service.subscriptions import save_subscriptions
from app.service.tasks import create_task, retry_task, update_task
from tests.conftest import seed_paper

SAMPLE_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <title>Example Atom Paper</title>
    <summary>Abstract text.</summary>
    <published>2024-01-01T00:00:00Z</published>
    <author><name>Alice</name></author>
    <category term="cs.CL"/>
  </entry>
</feed>
"""


def test_learning_service_branches(db_session) -> None:
    paper_id = seed_paper(db_session, arxiv_id="learn-br", title="Learning Branch")
    other_id = seed_paper(db_session, arxiv_id="learn-br-2", title="Learning Branch Two")

    comment, created = create_action(
        db_session,
        UserActionInput(
            user_id="svc-user",
            paper_id=paper_id,
            action_type="note",
            payload_json={"kind": "comment", "text": "Public comment"},
        ),
    )
    assert created is True
    assert comment.payload_json["visibility"] == "public"
    assert list_public_comments(db_session, paper_id)[0].id == comment.id

    private, _ = create_action(
        db_session,
        UserActionInput(
            user_id="svc-user",
            paper_id=other_id,
            action_type="note",
            payload_json={"kind": "note", "text": "Private note"},
        ),
    )
    assert private.payload_json["visibility"] == "private"

    first_fav, _ = create_action(
        db_session,
        UserActionInput(user_id="svc-user", paper_id=paper_id, action_type="favorite", payload_json={"favorite": True}),
    )
    second_fav, again = create_action(
        db_session,
        UserActionInput(user_id="svc-user", paper_id=paper_id, action_type="favorite", payload_json={"favorite": True}),
    )
    assert again is False
    assert second_fav.id == first_fav.id

    hist1, _ = create_action(
        db_session,
        UserActionInput(user_id="svc-user", paper_id=other_id, action_type="reading_history", payload_json={"section": "intro"}),
    )
    hist2, upserted = create_action(
        db_session,
        UserActionInput(user_id="svc-user", paper_id=other_id, action_type="reading_history", payload_json={"section": "method"}),
    )
    assert upserted is False
    assert hist2.id == hist1.id
    assert hist2.payload_json["section"] == "method"
    assert len(list_actions(db_session, "svc-user", None, "reading_history")) == 1

    updated = update_action(db_session, private.id, UserActionUpdate(payload_json={"kind": "note", "text": "Updated"}))
    assert updated.payload_json["text"] == "Updated"

    with pytest.raises(ValueError, match="ACTION_FORBIDDEN"):
        update_action(db_session, private.id, UserActionUpdate(payload_json={}), user_id="other-user")

    deleted_count = delete_actions_by_type(db_session, "svc-user", "note")
    assert deleted_count == 2
    delete_action(db_session, first_fav.id)
    delete_actions_by_type(db_session, "svc-user", "reading_history")
    assert list_actions(db_session, "svc-user", None, None) == []


def test_papers_service_reads_and_errors(db_session, monkeypatch) -> None:
    settings = Settings(environment="test", database_url="sqlite:///:memory:", search_agent_enabled=False)
    paper_id = seed_paper(db_session, arxiv_id="deep-read", title="Deep Read Paper", ingest_status="qa_ready")
    other_id = seed_paper(db_session, arxiv_id="deep-read-b", title="Deep Read Paper B", ingest_status="qa_ready")

    task, _ = create_task(db_session, paper_id, "full_parse", "deep-read-task")
    from app.service.tasks import save_results

    save_results(
        db_session,
        task.task_id,
        StructuredResultBatch(
            results=[
                StructuredResultInput(result_type="summary", content_json={"summary": "A transformer survey."}),
                StructuredResultInput(
                    result_type="concepts",
                    content_json={"items": [{"name": "Attention", "description": "token weighting"}]},
                ),
            ]
        ),
    )

    wiki = get_wiki(db_session, paper_id)
    assert wiki.summary == "A transformer survey."
    assert wiki.concepts

    assist = get_reading_assist(db_session, paper_id, mode="研究", force=True, settings=settings)
    assert assist.headline
    assert assist.sections

    compared = compare_papers(db_session, paper_id=paper_id, other_paper_id=other_id, settings=settings)
    assert compared.summary
    assert compared.paper_id == paper_id

    batch_upsert = [
        PaperUpsert(
            arxiv_id="deep-filter",
            title="Filtered Transformer Paper",
            authors=[AuthorInput(name="Alice Smith")],
            abstract="attention mechanism",
            primary_category="cs.CL",
            published_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
    ]
    from app.service.papers import batch_upsert_papers

    batch_upsert_papers(db_session, batch_upsert)

    page = search_papers(
        db_session,
        keyword="transformer",
        author="Alice",
        category="cs.CL",
        published_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        published_to=datetime(2024, 12, 31, tzinfo=timezone.utc),
        page=1,
        page_size=10,
        sort_by="published_desc",
    )
    assert page.total >= 1
    assert page.items

    smart = smart_search_papers(
        db_session,
        query="attention transformer",
        page=1,
        page_size=5,
        settings=settings,
        include_answer=False,
    )
    assert smart.search_session_id
    assert isinstance(smart.items, list)

    with pytest.raises(PaperServiceError) as exc:
        compare_papers(db_session, paper_id=paper_id, other_paper_id=paper_id, settings=settings)
    assert exc.value.code == "COMPARE_SAME_PAPER"


def test_tasks_service_branches(db_session) -> None:
    paper_id = seed_paper(db_session, arxiv_id="task-deep", title="Task Deep")
    task, _ = create_task(db_session, paper_id, "full_parse", "task-deep-key")

    running = update_task(db_session, task.task_id, TaskUpdate(status="running", stage="parse"))
    assert running.status == "running"

    failed = update_task(
        db_session,
        task.task_id,
        TaskUpdate(status="failed", error_code="PARSE_FAILED", stage="failed"),
    )
    assert failed.status == "failed"

    retried = retry_task(db_session, task.task_id)
    assert retried.status == "queued"
    assert retried.attempt == 2

    update_task(db_session, task.task_id, TaskUpdate(status="running", stage="parse"))
    update_task(
        db_session,
        task.task_id,
        TaskUpdate(status="failed", error_code="WORKER_ERROR", stage="failed"),
    )
    with pytest.raises(ValueError, match="TASK_RETRY_EXHAUSTED"):
        retry_task(db_session, task.task_id)


def test_recommendations_service(db_session) -> None:
    paper_id = seed_paper(
        db_session,
        arxiv_id="rec-deep",
        title="Recommendation Deep Paper",
        primary_category="cs.CL",
        ingest_status="qa_ready",
    )
    from app.model import Paper

    paper = db_session.get(Paper, paper_id)
    assert paper is not None
    paper.chunk_count = 2
    db_session.commit()

    daily = daily_picks(db_session, limit=3)
    assert isinstance(daily, list)

    profile = profile_recommendations(db_session, user_id="rec-user", limit=3)
    assert isinstance(profile, list)

    save_subscriptions(
        db_session,
        "rec-user",
        [{"type": "keyword", "value": "Transformer", "enabled": True}],
    )
    subs = subscription_recommendations(db_session, user_id="rec-user", limit=3)
    assert isinstance(subs, list)


def test_arxiv_client_http_retry(monkeypatch) -> None:
    client = ArxivClient(min_interval_s=0, max_retries=3, rate_limit_wait_s=0)
    calls = {"count": 0}

    def fake_urlopen(req, timeout=60):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", hdrs=None, fp=None)
        return type(
            "Resp",
            (),
            {
                "read": lambda self: SAMPLE_ATOM,
                "__enter__": lambda self: self,
                "__exit__": lambda *args: False,
            },
        )()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
    papers = client.search(search_query="cat:cs.CL", max_results=1)
    assert papers[0].arxiv_id == "2401.01234"
    assert calls["count"] == 2
    parsed = _parse_atom_feed(SAMPLE_ATOM)
    assert parsed[0].pdf_url.endswith("2401.01234.pdf")


def test_auth_and_search_http(client, user_headers, db_session) -> None:
    assert client.get("/api/auth/me").status_code == 401

    bad_login = client.post(
        "/api/auth/login",
        json={"email": "reader@example.com", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    assert client.post("/api/search/chunks", json={"query": "attention"}).status_code == 401

    paper_id = seed_paper(db_session, arxiv_id="search-http", title="Search HTTP Paper")
    from app.repository.chunks import upsert_chunks
    from app.schema.papers import TextChunkBatch, TextChunkInput

    upsert_chunks(
        db_session,
        paper_id,
        TextChunkBatch(chunks=[TextChunkInput(chunk_id="c1", page_no=1, content="attention model text")]),
    )
    ok = client.post(
        "/api/search/chunks",
        headers=user_headers,
        json={"query": "attention", "paper_id": paper_id, "top_k": 5},
    )
    assert ok.status_code == 200
    assert isinstance(ok.json()["data"]["chunks"], list)


def test_papers_http_error_branches(client, user_headers, db_session, monkeypatch) -> None:
    missing = client.get("/api/papers/99999/pdf", headers=user_headers)
    assert missing.status_code == 404

    paper_id = seed_paper(db_session, arxiv_id="pdf-http-404", title="PDF HTTP 404")

    def boom(session, pid, **kwargs):
        raise PaperServiceError("PDF_FETCH_FAILED", "拉取 PDF 失败（HTTP 404）", 502)

    monkeypatch.setattr("app.api.papers.load_paper_pdf_bytes", boom)
    response = client.get(f"/api/papers/{paper_id}/pdf", headers=user_headers)
    assert response.status_code == 502
    assert response.json()["code"] == "PDF_FETCH_FAILED"


def test_search_query_normalize_extended() -> None:
    assert infer_search_mode("1706.03762") == "arxiv"
    assert infer_search_mode("找一下沈备军老师的论文") == "author"
    hints = extract_author_candidates("找一下沈备军老师的论文")
    assert "Beijun Shen" in hints
    topics = expand_chinese_topics("多模态大模型")
    assert topics

    class _Paper:
        def __init__(self, title: str, abstract: str = "") -> None:
            self.title = title
            self.abstract = abstract

    assert paper_matches_excludes(_Paper("A survey of transformers", "overview"), ["survey"]) is True
    assert paper_matches_excludes(_Paper("A novel method", "experiments"), ["survey"]) is False
