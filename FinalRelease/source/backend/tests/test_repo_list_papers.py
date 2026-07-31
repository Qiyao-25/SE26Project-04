"""Repository list_papers filter branches."""

from datetime import datetime, timezone

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.repository.papers import filter_relevant_papers, find_title_candidates, list_papers
from app.schema.papers import AuthorInput, PaperUpsert
from app.repository.papers import upsert_paper


def test_list_papers_filters(tmp_path) -> None:
    engine = create_engine_for(Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'list.db'}"))
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        upsert_paper(
            session,
            PaperUpsert(
                arxiv_id="list-1",
                title="Deep Learning Survey",
                authors=[AuthorInput(name="Alice Smith")],
                abstract="neural networks survey",
                primary_category="cs.LG",
                published_at=datetime(2023, 6, 1, tzinfo=timezone.utc),
            ),
        )
        upsert_paper(
            session,
            PaperUpsert(
                arxiv_id="list-2",
                title="Transformer Paper",
                authors=[AuthorInput(name="Bob Lee")],
                abstract="attention is all you need style",
                primary_category="cs.CL",
                published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
        )

        papers, total = list_papers(
            session,
            keyword="transformer",
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=1,
            page_size=10,
            search_field="title",
        )
        assert total >= 1

        by_author, total_a = list_papers(
            session,
            keyword="Alice",
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=1,
            page_size=10,
            search_field="author",
        )
        assert total_a >= 1

        by_cat, total_c = list_papers(
            session,
            keyword=None,
            author=None,
            category="cs.LG",
            published_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
            published_to=datetime(2023, 12, 31, tzinfo=timezone.utc),
            page=1,
            page_size=10,
        )
        assert total_c >= 1

        candidates = find_title_candidates(session, "Deep Learning", limit=5)
        assert candidates
        ranked = filter_relevant_papers(papers, keywords=["transformer"], query="transformer")
        assert ranked
