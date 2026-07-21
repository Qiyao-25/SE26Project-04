from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import BackgroundTasks
from starlette.requests import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.papers import parse
from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, Paper
from app.schema.auth import AuthUser
from app.schema.papers import AuthorInput, PaperUpsert, ParseRequest
from app.service.papers import batch_upsert_papers, get_paper_detail, get_paper_graph, get_wiki


def make_session() -> Session:
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return Session(engine)


def paper_payload(arxiv_id: str = "1706.03762", title: str = "Attention Is All You Need") -> PaperUpsert:
    return PaperUpsert(
        arxiv_id=arxiv_id,
        title=title,
        authors=[AuthorInput(name="Vaswani"), AuthorInput(name="Shazeer")],
        abstract="Transformer architecture based on attention.",
        primary_category="cs.CL",
    )


def test_batch_upsert_deduplicates_by_arxiv_id() -> None:
    with make_session() as session:
        # Different titles so title-normalize merge does not collapse distinct arXiv IDs.
        result = batch_upsert_papers(
            session,
            [
                paper_payload("1706.03762", "Attention Is All You Need"),
                paper_payload("1810.04805", "BERT: Pre-training of Deep Bidirectional Transformers"),
            ],
        )
        assert result.created == 2
        result = batch_upsert_papers(session, [paper_payload(title="Updated title")])
        assert result.created == 0
        assert result.updated == 1
        assert session.scalar(select(Paper).where(Paper.title == "Updated title")) is not None


def test_batch_upsert_keeps_same_title_different_arxiv_id() -> None:
    """Distinct arXiv records must not be merged just because titles collide."""
    with make_session() as session:
        first = batch_upsert_papers(session, [paper_payload("1706.03762", "Same Title Paper")])
        second = batch_upsert_papers(session, [paper_payload("9999.99999", "Same Title Paper")])
        assert first.created == 1
        assert second.created == 1
        assert second.updated == 0
        assert session.scalar(select(func.count()).select_from(Paper).where(Paper.deleted_at.is_(None))) == 2


def test_paper_detail_and_wiki_return_contract() -> None:
    with make_session() as session:
        batch_upsert_papers(session, [paper_payload()])
        detail = get_paper_detail(session, 1)
        assert detail.arxiv_id == "1706.03762"
        wiki = get_wiki(session, 1)
        assert wiki.summary == ""
        assert wiki.concepts == []
        assert wiki.methods == []


def test_openapi_contains_paper_contract() -> None:
    from app.main import create_app

    app = create_app(Settings(environment="test", database_url="sqlite:///:memory:"))
    paths = app.openapi()["paths"]
    assert "/api/papers" in paths
    assert "/api/papers/{paper_id}" in paths
    assert "/api/papers/{paper_id}/wiki" in paths


def test_parse_endpoint_schedules_background_job() -> None:
    settings = Settings(environment="test", database_url="sqlite:///:memory:")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, engine=engine))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/papers/1/parse",
        "headers": [],
        "client": ("test", 0),
        "server": ("test", 80),
        "scheme": "http",
        "query_string": b"",
        "root_path": "",
        "app": app,
    }
    request = Request(scope)
    request.state.request_id = "parse-test-request"

    with Session(engine) as session:
        paper_id = batch_upsert_papers(session, [paper_payload()]).items[0].paper_id
        background_tasks = BackgroundTasks()
        result = parse(
            paper_id,
            ParseRequest(),
            request,
            background_tasks,
            "parse-test-key",
            session,
            AuthUser(user_id="1", email="u@example.com", role="user"),
        )

    assert result.data.paper_id == paper_id
    assert result.data.status == "queued"
    assert len(background_tasks.tasks) == 1


def test_paper_graph_refresh_persists_and_reuses_related_papers() -> None:
    settings = Settings(environment="test", database_url="sqlite:///:memory:")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        current = PaperUpsert(
            arxiv_id="graph-current",
            title="Attention Model",
            abstract="An attention model evaluated on GLUE benchmark tasks.",
            primary_category="cs.CL",
            published_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        related = PaperUpsert(
            arxiv_id="graph-related",
            title="Earlier Attention Model",
            abstract="An earlier attention encoder.",
            primary_category="cs.CL",
            published_at=datetime(2019, 1, 1, tzinfo=timezone.utc),
        )
        current_id = batch_upsert_papers(session, [current, related]).items[0].paper_id

        refreshed = get_paper_graph(session, current_id, settings=settings, force=True)
        reused = get_paper_graph(session, current_id, settings=settings, force=False)

    assert any(node.paper_id and node.paper_id != current_id for node in refreshed.nodes)
    assert any(edge.type == "precedes" for edge in refreshed.edges)
    assert reused.model_dump() == refreshed.model_dump()
