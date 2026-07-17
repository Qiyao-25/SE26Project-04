from app.schema.paper import SearchRequest
from app.schema.qa import AskPaperRequest
from app.service.paper import require_content, require_paper, require_summary, search_papers
from app.service.qa import ask_paper


def test_batch_endpoint_accepts_pipeline_wrapper() -> None:
    from app.core.config import Settings
    from app.core.database import create_engine_for
    from app.model import Base
    from app.schema.papers import AuthorInput, PaperUpsert
    from app.service.papers import batch_upsert_papers
    from sqlalchemy.orm import Session

    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    payload = PaperUpsert(arxiv_id="1706.03762", title="Attention", authors=[AuthorInput(display_name="Vaswani")])
    with Session(engine) as session:
        result = batch_upsert_papers(session, [payload])
    assert result.created == 1
    assert result.items[0].authors == ["Vaswani"]


def test_search_and_detail_flow() -> None:
    result = search_papers(SearchRequest(query="Transformer", page=1, pageSize=12))
    assert result.total >= 2
    assert any(item.paperId == "attention" for item in result.items)
    detail = require_paper("attention")
    assert detail.arxivId == "1706.03762"


def test_content_summary_and_qa_flow() -> None:
    assert require_content("attention").paperId == "attention"
    assert require_summary("attention").paperId == "attention"
    result = ask_paper("attention", AskPaperRequest(question="这篇论文的方法是什么？"))
    assert result.citations


def test_not_found() -> None:
    for resolver in (require_paper, require_content, require_summary):
        try:
            resolver("not-found")
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing paper")
