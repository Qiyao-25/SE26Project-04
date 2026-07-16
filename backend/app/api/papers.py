from fastapi import APIRouter, HTTPException, Request

from app.schema.common import ApiResponse
from app.schema.paper import PaperContent, PaperDetail, PaperSummary, SearchRequest, SearchResult
from app.schema.qa import AskPaperRequest, AskPaperResult
from app.service.paper import require_content, require_paper, require_summary, search_papers
from app.service.qa import ask_paper

router = APIRouter(prefix="/api/papers", tags=["papers"])


def _not_found(paper_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"论文不存在：{paper_id}")


@router.post("/search", response_model=ApiResponse[SearchResult], summary="检索固定样例论文")
def search(payload: SearchRequest, request: Request) -> ApiResponse[SearchResult]:
    return ApiResponse(data=search_papers(payload), request_id=request.state.request_id)


@router.get("/{paper_id}/content", response_model=ApiResponse[PaperContent], summary="获取论文原文入口")
def content(paper_id: str, request: Request) -> ApiResponse[PaperContent]:
    try:
        data = require_content(paper_id)
    except KeyError as exc:
        raise _not_found(paper_id) from exc
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}/summary", response_model=ApiResponse[PaperSummary], summary="获取结构化摘要")
def summary(paper_id: str, request: Request) -> ApiResponse[PaperSummary]:
    try:
        data = require_summary(paper_id)
    except KeyError as exc:
        raise _not_found(paper_id) from exc
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/qa", response_model=ApiResponse[AskPaperResult], summary="单论文问答")
def qa(paper_id: str, payload: AskPaperRequest, request: Request) -> ApiResponse[AskPaperResult]:
    try:
        data = ask_paper(paper_id, payload)
    except KeyError as exc:
        raise _not_found(paper_id) from exc
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}", response_model=ApiResponse[PaperDetail], summary="获取论文详情")
def detail(paper_id: str, request: Request) -> ApiResponse[PaperDetail]:
    try:
        data = require_paper(paper_id)
    except KeyError as exc:
        raise _not_found(paper_id) from exc
    return ApiResponse(data=data, request_id=request.state.request_id)
