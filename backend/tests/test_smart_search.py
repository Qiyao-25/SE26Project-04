from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import PaperUpsert
from app.service.papers import batch_upsert_papers, smart_search_papers
from sqlalchemy.orm import Session


def test_smart_search_uses_database_papers_without_llm() -> None:
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        batch_upsert_papers(
            session,
            [
                PaperUpsert(
                    arxiv_id="attention-1",
                    title="Transformer Attention for Language Modeling",
                    abstract="A study of self-attention and Transformer representations.",
                ),
                PaperUpsert(
                    arxiv_id="retrieval-1",
                    title="Retrieval Augmented Generation",
                    abstract="A retrieval system for knowledge-intensive generation.",
                ),
            ],
        )

        result = smart_search_papers(
            session,
            query="attention transformer",
            page=1,
            page_size=12,
            settings=Settings(
                environment="test",
                database_url="sqlite:///:memory:",
                search_agent_enabled=False,
                llm_api_key="",
            ),
        )

    assert result.total == 1
    assert result.items[0].arxiv_id == "attention-1"
    assert result.answer_source == "template"
