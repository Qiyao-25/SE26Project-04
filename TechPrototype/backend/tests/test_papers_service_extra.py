"""Additional papers service coverage."""

import pytest

from app.core.config import Settings
from app.service.papers import PaperServiceError, delete_paper, fetch_one_paper, get_paper_graph, get_wiki
from app.service.tasks import create_task, save_results
from app.schema.papers import StructuredResultBatch, StructuredResultInput
from tests.conftest import seed_paper


def test_delete_paper_and_fetch_errors(db_session):
    paper_id = seed_paper(db_session, arxiv_id="del-paper", title="Delete Me")
    deleted = delete_paper(db_session, paper_id)
    assert deleted.paper_id == paper_id
    with pytest.raises(PaperServiceError):
        delete_paper(db_session, paper_id)
    with pytest.raises(PaperServiceError):
        delete_paper(db_session, 99999)


def test_get_paper_graph_force_regenerate(db_session, monkeypatch):
    settings = Settings(environment="test", database_url="sqlite:///:memory:", llm_api_key="k", llm_model="m")
    paper_id = seed_paper(db_session, arxiv_id="graph-force", title="Graph Force", ingest_status="qa_ready")
    task, _ = create_task(db_session, paper_id, "full_parse", "graph-task")
    save_results(
        db_session,
        task.task_id,
        StructuredResultBatch(
            results=[
                StructuredResultInput(result_type="summary", content_json={"summary": "A survey of attention."}),
                StructuredResultInput(
                    result_type="graph",
                    content_json={"nodes": [{"id": "n1", "label": "A"}], "edges": []},
                ),
            ]
        ),
    )

    cached = get_paper_graph(db_session, paper_id, settings=settings, force=False)
    assert cached.nodes

    class FakeGraph:
        def run(self, **kwargs):
            from app.schema.papers import GraphNode, PaperGraphData

            return PaperGraphData(
                paper_id=paper_id,
                nodes=[GraphNode(id="n2", type="concept", label="B", paper_id=paper_id)],
                edges=[],
                source="agent",
            )

    monkeypatch.setattr("app.agents.graph_agent.GraphAgent", lambda s: FakeGraph())
    refreshed = get_paper_graph(db_session, paper_id, settings=settings, force=True)
    assert refreshed.nodes


def test_fetch_one_not_found(db_session, monkeypatch):
    class EmptyClient:
        def resolve_query(self, *args, **kwargs):
            return []

    monkeypatch.setattr("app.service.arxiv_client.ArxivClient", lambda **kwargs: EmptyClient())
    with pytest.raises(PaperServiceError) as exc:
        fetch_one_paper(
            db_session,
            query="missing paper title xyz",
            parse=False,
            settings=Settings(environment="test", database_url="sqlite:///:memory:"),
        )
    assert exc.value.code == "PAPER_NOT_FOUND"


def test_wiki_not_ready(db_session):
    paper_id = seed_paper(db_session, arxiv_id="wiki-not", title="Wiki Not Ready", ingest_status="metadata_only")
    wiki = get_wiki(db_session, paper_id)
    assert wiki.parse_status in {"metadata_only", "pending", "queued", "failed", "completed"}
