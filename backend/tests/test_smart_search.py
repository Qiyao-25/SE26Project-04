from app.agents.search_agent import SearchAgent
from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import AuthorInput, PaperUpsert
from app.service.papers import batch_upsert_papers, smart_search_papers
from app.service.search_query_normalize import (
    extract_author_candidates,
    infer_search_mode,
    romanize_chinese_person_name,
)
from sqlalchemy.orm import Session


def _settings(**kwargs) -> Settings:
    settings = Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        search_agent_enabled=False,
        llm_api_key="",
        agent_api_key=None,
        deepseek_api_key="",
        **kwargs,
    )
    settings.llm_api_key = ""
    settings.search_agent_enabled = False
    return settings


def test_romanize_shen_beijun() -> None:
    variants = romanize_chinese_person_name("沈备军")
    assert "Beijun Shen" in variants
    assert "Shen" in variants


def test_extract_author_from_natural_chinese_query() -> None:
    authors = extract_author_candidates("找一下沈备军老师的论文")
    assert authors[0] == "Beijun Shen"
    assert infer_search_mode("找一下沈备军老师的论文") == "author"


def test_search_agent_heuristic_author_plan() -> None:
    agent = SearchAgent(_settings())
    plan = agent.plan("找一下沈备军老师的论文")
    assert plan.search_mode == "author"
    assert "Beijun Shen" in plan.author_hints
    assert plan.rewritten_query == "Beijun Shen"


def test_smart_search_matches_english_author_from_chinese_query() -> None:
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        batch_upsert_papers(
            session,
            [
                PaperUpsert(
                    arxiv_id="shen-1",
                    title="Software Engineering with Large Language Models",
                    abstract="A survey of LLM applications in software engineering.",
                    authors=[AuthorInput(name="Beijun Shen"), AuthorInput(name="Alice Example")],
                    primary_category="cs.SE",
                ),
                PaperUpsert(
                    arxiv_id="other-1",
                    title="Transformer Attention for Language Modeling",
                    abstract="A study of self-attention and Transformer representations.",
                    authors=[AuthorInput(name="Bob Other")],
                    primary_category="cs.CL",
                ),
            ],
        )

        result = smart_search_papers(
            session,
            query="找一下沈备军老师的论文",
            page=1,
            page_size=12,
            settings=_settings(),
        )

    assert result.search_mode == "author"
    assert "Beijun Shen" in result.author_hints
    assert result.total >= 1
    assert result.items[0].arxiv_id == "shen-1"


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
            settings=_settings(),
        )

    assert result.total == 1
    assert result.items[0].arxiv_id == "attention-1"
    assert result.answer_source == "template"
