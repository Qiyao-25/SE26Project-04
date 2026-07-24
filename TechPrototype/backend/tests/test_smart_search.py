from app.agents.search_agent import SearchAgent
from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import AuthorInput, PaperUpsert
from app.service.papers import batch_upsert_papers, smart_search_papers
from app.service.search_query_normalize import (
    expand_term_aliases,
    extract_exclude_terms,
    extract_year_range,
    resolve_author_hints,
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


def test_resolve_known_author_verified() -> None:
    hints, verified, warnings = resolve_author_hints("找一下沈备军老师的论文")
    assert "Beijun Shen" in hints
    assert verified is True
    assert "AUTHOR_TRANSLITERATION_UNVERIFIED" not in warnings


def test_term_lexicon_rag() -> None:
    canonical, aliases, cats = expand_term_aliases("检索增强生成和 RAG")
    assert "retrieval augmented generation" in canonical
    assert any(item.upper() == "RAG" or item == "RAG" for item in aliases)
    assert cats


def test_exclude_and_year_parsing() -> None:
    assert "survey" in extract_exclude_terms("不要综述的 LoRA 论文")
    year_from, year_to = extract_year_range("近几年多模态进展")
    assert year_from is not None and year_to is not None
    assert year_to - year_from <= 3


def test_search_agent_heuristic_author_plan() -> None:
    agent = SearchAgent(_settings())
    plan = agent.plan("找一下沈备军老师的论文")
    assert plan.search_mode == "author"
    assert "Beijun Shen" in plan.author_hints
    assert plan.author_verified is True


def test_smart_search_session_pagination() -> None:
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        batch_upsert_papers(
            session,
            [
                PaperUpsert(
                    arxiv_id=f"att-{index}",
                    title=f"Transformer Attention Study {index}",
                    abstract="A study of self-attention and Transformer representations.",
                )
                for index in range(1, 6)
            ],
        )
        first = smart_search_papers(
            session,
            query="attention transformer",
            page=1,
            page_size=2,
            settings=_settings(),
        )
        assert first.search_session_id
        assert first.total >= 2
        second = smart_search_papers(
            session,
            query="attention transformer",
            page=2,
            page_size=2,
            search_session_id=first.search_session_id,
            include_answer=False,
            settings=_settings(),
        )
        assert second.total == first.total
        assert second.plan_source in {"reused", "heuristic", "llm"}
        first_ids = {item.paper_id for item in first.items}
        second_ids = {item.paper_id for item in second.items}
        assert first_ids.isdisjoint(second_ids)


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
    assert result.search_session_id


def test_full_title_paste_hits_exact_paper() -> None:
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    full_title = (
        "Overlaying Governance: A Compositional Authorization Framework "
        "for Delegation and Scope in Agentic AI"
    )

    with Session(engine) as session:
        # Noise papers that share common title words (framework / for / and / scope).
        noise = [
            PaperUpsert(
                arxiv_id=f"noise-{index}",
                title=f"A Framework for Scope and Delegation Study {index}",
                abstract="Generic framework paper about delegation and scope.",
            )
            for index in range(1, 40)
        ]
        batch_upsert_papers(
            session,
            [
                *noise,
                PaperUpsert(
                    arxiv_id="overlay-1",
                    title=full_title,
                    abstract="Authorization framework for agentic AI governance.",
                ),
            ],
        )

        full = smart_search_papers(
            session,
            query=full_title,
            page=1,
            page_size=12,
            settings=_settings(),
        )
        short = smart_search_papers(
            session,
            query="Overlaying Governance",
            page=1,
            page_size=12,
            settings=_settings(),
        )

    assert full.total >= 1
    assert full.items[0].arxiv_id == "overlay-1"
    assert short.total >= 1
    assert short.items[0].arxiv_id == "overlay-1"


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
