from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import ChunkSearchRequest, PaperUpsert, TextChunkBatch, TextChunkInput
from app.schema.qa import AskPaperResult
from app.api.papers import _qa_payload
from app.service.papers import PaperServiceError, answer_question, batch_upsert_papers
from app.repository.chunks import search_chunks, upsert_chunks
from sqlalchemy.orm import Session


def make_session() -> Session:
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return Session(engine)


def agent_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        qa_agent_enabled=True,
        llm_api_key="test-key",
        llm_model="test-model",
    )


def patch_citation_agent(monkeypatch) -> None:
    from app.agents.qa_agent import QaAgentResult
    import app.service.papers as papers_service

    monkeypatch.setattr(
        papers_service,
        "QaAgent",
        lambda _settings: type("FakeQaAgent", (), {
            "run": lambda self, **_kwargs: QaAgentResult(
                "The transformer uses multi-head attention.", ["c001"], False,
            ),
        })(),
    )


def test_chunk_write_search_and_qa_citations(monkeypatch) -> None:
    patch_citation_agent(monkeypatch)
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="chunk-paper", title="Chunk Paper", abstract="fallback")]).items[0]
        upsert_chunks(session, paper.paper_id, TextChunkBatch(chunks=[TextChunkInput(chunk_id="c001", page_no=2, section="Method", content="The transformer uses multi-head attention.")]))
        matches = search_chunks(session, ChunkSearchRequest(paper_id=paper.paper_id, query="multi-head attention", top_k=3))
        assert matches[0][0].chunk_id == "c001"
        answer = answer_question(session, paper.paper_id, "multi-head attention", settings=agent_settings())
        assert answer.citations[0]["pageNumber"] == 2


def test_retrieval_handles_inflected_contribution_question() -> None:
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="contribution-search", title="Contribution Search", abstract="abstract")]).items[0]
        upsert_chunks(
            session,
            paper.paper_id,
            TextChunkBatch(chunks=[TextChunkInput(
                chunk_id="c001",
                page_no=1,
                section="Introduction",
                content="Our contributions introduce a lightweight architecture and improve the model performance.",
            )]),
        )
        matches = search_chunks(
            session,
            ChunkSearchRequest(paper_id=paper.paper_id, query="What is the main contribution?", top_k=3),
        )
        assert matches
        assert matches[0][1] >= 0.08


def test_chinese_agent_summary_can_cite_english_evidence(monkeypatch) -> None:
    from app.agents.qa_agent import QaAgentResult
    import app.service.papers as papers_service

    monkeypatch.setattr(
        papers_service,
        "QaAgent",
        lambda _settings: type("FakeQaAgent", (), {
            "run": lambda self, **_kwargs: QaAgentResult(
                "根据原文，该方法使用多头注意力来进行表示学习。", ["c001"], False,
            ),
        })(),
    )
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="cross-language-citation", title="Cross Language Citation", abstract="abstract")]).items[0]
        upsert_chunks(
            session,
            paper.paper_id,
            TextChunkBatch(chunks=[TextChunkInput(
                chunk_id="c001",
                page_no=1,
                section="Method",
                content="The model uses multi-head attention for representation learning.",
            )]),
        )
        result = answer_question(session, paper.paper_id, "multi-head attention", settings=agent_settings())
        assert result.citations[0]["sectionId"] == "c001"


def test_qa_without_chunk_evidence_is_rejected() -> None:
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="no-chunk-paper", title="No Chunk", abstract="abstract")]).items[0]
        try:
            answer_question(session, paper.paper_id, "unsupported fact")
        except PaperServiceError as exc:
            assert exc.code == "NO_EVIDENCE"
            assert exc.status_code == 422
        else:
            raise AssertionError("expected NO_EVIDENCE")


def test_qa_rejects_structured_result_without_original_chunks() -> None:
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="structured-only", title="Structured Only", abstract="abstract")]).items[0]
        from app.schema.papers import StructuredResultBatch, StructuredResultInput
        from app.service.tasks import create_task, save_results

        task, _ = create_task(session, paper.paper_id, "full_parse", "structured-only-task")
        save_results(session, task.task_id, StructuredResultBatch(results=[StructuredResultInput(result_type="summary", content_json={"summary": "summary"})]))
        try:
            answer_question(session, paper.paper_id, "unsupported fact")
        except PaperServiceError as exc:
            assert exc.code == "NO_EVIDENCE"
            assert exc.status_code == 422
        else:
            raise AssertionError("expected NO_EVIDENCE")


def test_qa_rejects_weak_long_chunk_without_query_match() -> None:
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="weak-evidence", title="Weak Evidence", abstract="abstract")]).items[0]
        upsert_chunks(
            session,
            paper.paper_id,
            TextChunkBatch(chunks=[TextChunkInput(
                chunk_id="c001",
                page_no=1,
                section="Introduction",
                content="This is a long paragraph about an unrelated optimization benchmark and its training setup. " * 8,
            )]),
        )
        try:
            answer_question(session, paper.paper_id, "quantum entanglement theorem")
        except PaperServiceError as exc:
            assert exc.code == "NO_EVIDENCE"
            assert exc.status_code == 422
        else:
            raise AssertionError("expected NO_EVIDENCE")


def test_qa_rejects_non_paper_question_in_chinese() -> None:
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="non-paper-question", title="Non Paper Question", abstract="abstract")]).items[0]
        upsert_chunks(
            session,
            paper.paper_id,
            TextChunkBatch(chunks=[TextChunkInput(
                chunk_id="c001",
                page_no=1,
                section="Method",
                content="The transformer uses multi-head attention for representation learning.",
            )]),
        )
        try:
            answer_question(session, paper.paper_id, "我今晚吃什么")
        except PaperServiceError as exc:
            assert exc.code == "NO_EVIDENCE"
            assert exc.status_code == 422
        else:
            raise AssertionError("expected NO_EVIDENCE")


def test_qa_rejects_agent_answer_without_valid_citation(monkeypatch) -> None:
    from app.agents.qa_agent import QaAgentResult
    import app.service.papers as papers_service

    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="agent-no-citation", title="Agent No Citation", abstract="abstract")]).items[0]
        upsert_chunks(
            session,
            paper.paper_id,
            TextChunkBatch(chunks=[TextChunkInput(
                chunk_id="c001",
                page_no=1,
                section="Method",
                content="The model uses multi-head attention for representation learning.",
            )]),
        )
        monkeypatch.setattr(
            papers_service,
            "QaAgent",
            lambda _settings: type("FakeQaAgent", (), {"run": lambda self, **_kwargs: QaAgentResult("unsupported answer", ["c001"], False)})(),
        )
        settings = Settings(
            environment="test",
            database_url="sqlite:///:memory:",
            qa_agent_enabled=True,
            llm_api_key="test-key",
            llm_model="test-model",
        )
        try:
            answer_question(session, paper.paper_id, "multi-head attention", settings=settings)
        except PaperServiceError as exc:
            assert exc.code == "NO_EVIDENCE"
            assert exc.status_code == 422
        else:
            raise AssertionError("expected NO_EVIDENCE")


def test_qa_api_payload_normalizes_numeric_citation_paper_id(monkeypatch) -> None:
    patch_citation_agent(monkeypatch)
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="qa-contract-paper", title="QA Contract")]).items[0]
        upsert_chunks(session, paper.paper_id, TextChunkBatch(chunks=[TextChunkInput(chunk_id="c001", page_no=1, section="Intro", content="The model uses attention for representation learning.")]))
        result = answer_question(session, paper.paper_id, "attention", settings=agent_settings())
        payload = _qa_payload(result, history_count=0)
        validated = AskPaperResult.model_validate(payload)
        assert validated.paperId == str(paper.paper_id)
        assert validated.citations[0].paperId == str(paper.paper_id)


def test_qa_does_not_use_extractive_fallback_when_agent_unavailable() -> None:
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="agent-required", title="Agent Required", abstract="abstract")]).items[0]
        upsert_chunks(
            session,
            paper.paper_id,
            TextChunkBatch(chunks=[TextChunkInput(
                chunk_id="c001",
                page_no=1,
                section="Method",
                content="The model uses attention for representation learning.",
            )]),
        )
        try:
            answer_question(session, paper.paper_id, "attention")
        except PaperServiceError as exc:
            assert exc.code == "QA_AGENT_UNAVAILABLE"
            assert exc.status_code == 503
        else:
            raise AssertionError("expected QA_AGENT_UNAVAILABLE")
