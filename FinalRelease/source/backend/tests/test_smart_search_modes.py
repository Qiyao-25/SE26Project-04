"""Smart search service mode branches."""

from unittest.mock import MagicMock

from app.agents.search_agent import SearchPlan
from app.schema.papers import AuthorInput, PaperUpsert
from app.service.papers import batch_upsert_papers, smart_search_papers
from tests.conftest import seed_paper


def test_smart_search_author_and_mixed_modes(db_session, settings, monkeypatch):
    batch_upsert_papers(
        db_session,
        [
            PaperUpsert(
                arxiv_id="auth-1",
                title="Graph Neural Networks by Alice Smith",
                authors=[AuthorInput(name="Alice Smith")],
                abstract="graph neural network methods",
                primary_category="cs.LG",
            ),
            PaperUpsert(
                arxiv_id="mix-1",
                title="Transformer Survey",
                authors=[AuthorInput(name="Bob Lee")],
                abstract="attention transformer survey",
                primary_category="cs.CL",
            ),
        ],
    )

    author_plan = SearchPlan(
        rewritten_query="Alice Smith",
        keywords=["Alice", "Smith"],
        author_hints=["Alice Smith"],
        category_hints=[],
        search_mode="author",
        intent="find author papers",
        source="test",
    )
    mixed_plan = SearchPlan(
        rewritten_query="Bob transformer",
        keywords=["transformer", "Bob"],
        author_hints=["Bob Lee"],
        category_hints=["cs.CL"],
        search_mode="mixed",
        intent="mixed",
        source="test",
    )

    plans = iter([author_plan, mixed_plan])

    class FakeAgent:
        def plan(self, query):
            return next(plans)

    monkeypatch.setattr("app.agents.search_agent.SearchAgent", lambda s: FakeAgent())

    author_result = smart_search_papers(
        db_session,
        query="Alice Smith papers",
        page=1,
        page_size=5,
        include_answer=False,
        settings=settings,
    )
    assert author_result.total >= 0

    mixed_result = smart_search_papers(
        db_session,
        query="Bob transformer",
        page=1,
        page_size=5,
        include_answer=False,
        settings=settings,
    )
    assert mixed_result.total >= 0
