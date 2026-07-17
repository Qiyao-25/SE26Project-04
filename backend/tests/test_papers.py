from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, Paper
from app.schema.papers import AuthorInput, PaperUpsert
from app.service.papers import batch_upsert_papers, get_paper_detail, get_wiki


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
        result = batch_upsert_papers(session, [paper_payload(), paper_payload("1810.04805")])
        assert result.created == 2
        result = batch_upsert_papers(session, [paper_payload(title="Updated title")])
        assert result.created == 0
        assert result.updated == 1
        assert session.scalar(select(Paper).where(Paper.title == "Updated title")) is not None


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
