from app.schema.paper import SearchRequest
from app.schema.qa import AskPaperRequest
from app.service.paper import require_content, require_paper, require_summary, search_papers
from app.service.qa import ask_paper


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
