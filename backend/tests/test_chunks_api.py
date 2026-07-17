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


def test_chunk_write_search_and_qa_citations() -> None:
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="chunk-paper", title="Chunk Paper", abstract="fallback")]).items[0]
        upsert_chunks(session, paper.paper_id, TextChunkBatch(chunks=[TextChunkInput(chunk_id="c001", page_no=2, section="Method", content="The transformer uses multi-head attention.")]))
        matches = search_chunks(session, ChunkSearchRequest(paper_id=paper.paper_id, query="multi-head attention", top_k=3))
        assert matches[0][0].chunk_id == "c001"
        answer = answer_question(session, paper.paper_id, "multi-head attention")
        assert answer.citations[0]["pageNumber"] == 2


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


def test_qa_api_payload_normalizes_numeric_citation_paper_id() -> None:
    with make_session() as session:
        paper = batch_upsert_papers(session, [PaperUpsert(arxiv_id="qa-contract-paper", title="QA Contract")]).items[0]
        upsert_chunks(session, paper.paper_id, TextChunkBatch(chunks=[TextChunkInput(chunk_id="c001", page_no=1, section="Intro", content="The model uses attention for representation learning.")]))
        result = answer_question(session, paper.paper_id, "attention")
        payload = _qa_payload(result, history_count=0)
        validated = AskPaperResult.model_validate(payload)
        assert validated.paperId == str(paper.paper_id)
        assert validated.citations[0].paperId == str(paper.paper_id)
