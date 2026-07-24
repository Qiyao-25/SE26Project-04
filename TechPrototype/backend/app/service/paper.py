from time import perf_counter
from uuid import uuid4

from app.repository.paper import get_paper, get_paper_content, get_paper_summary, list_papers
from app.schema.paper import PaperContent, PaperDetail, PaperSummary, SearchRequest, SearchResult


def search_papers(request: SearchRequest) -> SearchResult:
    started_at = perf_counter()
    normalized_query = request.query.strip().lower()
    items = []

    for paper in list_papers():
        if request.categories and paper["primaryCategory"] not in request.categories:
            continue

        searchable_text = " ".join(
            [
                paper["title"],
                paper["summary"],
                paper["primaryCategory"],
                paper["arxivId"],
                paper["researchDirection"],
                *paper["authors"],
                *paper["keywords"],
                *paper["conceptTags"],
            ]
        ).lower()

        if normalized_query and normalized_query not in searchable_text:
            continue

        items.append(paper)

    if request.sortBy == "date":
        items.sort(key=lambda item: item["publishedAt"], reverse=True)

    total = len(items)
    start = (request.page - 1) * request.pageSize
    elapsed_ms = max(1, round((perf_counter() - started_at) * 1000))

    return SearchResult(
        searchId=f"search-{uuid4()}",
        query=request.query,
        searchType=request.searchType,
        sortBy=request.sortBy,
        total=total,
        page=request.page,
        pageSize=request.pageSize,
        searchTimeMs=elapsed_ms,
        items=items[start : start + request.pageSize],
    )


def require_paper(paper_id: str) -> PaperDetail:
    paper = get_paper(paper_id)
    if not paper:
        raise KeyError(paper_id)
    return PaperDetail.model_validate(paper)


def require_content(paper_id: str) -> PaperContent:
    content = get_paper_content(paper_id)
    if not content:
        raise KeyError(paper_id)
    return PaperContent.model_validate(content)


def require_summary(paper_id: str) -> PaperSummary:
    summary = get_paper_summary(paper_id)
    if not summary:
        raise KeyError(paper_id)
    return PaperSummary.model_validate(summary)
