from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schema.common import ApiResponse
from app.schema.paper import PaperContent, PaperDetail, PaperSummary, SearchRequest, SearchResult
from app.schema.papers import BatchUpsertResponse, PaperItem, PaperPage, PaperUpsert, QaRequest, WikiData
from app.schema.qa import AskPaperRequest, AskPaperResult
from app.service.paper import require_content, require_paper, require_summary, search_papers as search_mock_papers
from app.service.papers import PaperServiceError, answer_question, batch_upsert_papers, get_paper_detail, get_wiki, search_papers
from app.service.qa import ask_paper

router = APIRouter(prefix="/api/papers", tags=["papers"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


def _not_found(request: Request, paper_id: str):
    return JSONResponse(status_code=404, content={"code": "PAPER_NOT_FOUND", "message": f"论文不存在：{paper_id}", "data": {}, "request_id": request.state.request_id})


def _db_error(request: Request, error: PaperServiceError):
    body = ApiResponse[dict](code=error.code, message=error.message, data={}, request_id=request.state.request_id)
    return JSONResponse(status_code=error.status_code, content=body.model_dump())


@router.get("", response_model=ApiResponse[PaperPage], summary="检索数据库论文元数据")
def papers(
    request: Request,
    db: Session = Depends(db_session),
    keyword: str | None = Query(default=None, max_length=200),
    author: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=128),
    published_from: datetime | None = None,
    published_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
):
    data = search_papers(db, keyword=keyword, author=author, category=category, published_from=published_from, published_to=published_to, page=page, page_size=page_size)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/batch", response_model=ApiResponse[BatchUpsertResponse], summary="批量去重写入论文元数据")
def batch_papers(request: Request, payload: list[PaperUpsert], db: Session = Depends(db_session)):
    try:
        data = batch_upsert_papers(db, payload)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/search", response_model=ApiResponse[SearchResult], summary="检索固定样例论文")
def search(payload: SearchRequest, request: Request) -> ApiResponse[SearchResult]:
    return ApiResponse(data=search_mock_papers(payload), request_id=request.state.request_id)


@router.get("/{paper_id}/content", response_model=ApiResponse[PaperContent], summary="获取论文原文入口")
def content(paper_id: str, request: Request, db: Session = Depends(db_session)):
    if paper_id.isdigit():
        try:
            paper = get_paper_detail(db, int(paper_id))
        except PaperServiceError as exc:
            return _db_error(request, exc)
        return ApiResponse(data=PaperContent(paperId=str(paper.paper_id), contentType="pdf", pdfUrl=paper.pdf_url, defaultPage=1, sections=[]), request_id=request.state.request_id)
    try:
        data = require_content(paper_id)
    except KeyError:
        return _not_found(request, paper_id)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}/summary", response_model=ApiResponse[PaperSummary], summary="获取结构化摘要")
def summary(paper_id: str, request: Request, db: Session = Depends(db_session)):
    if paper_id.isdigit():
        try:
            wiki = get_wiki(db, int(paper_id))
        except PaperServiceError as exc:
            return _db_error(request, exc)
        data = PaperSummary(
            paperId=str(wiki.paper_id),
            parseStatus=wiki.parse_status,
            summary=wiki.summary or "",
            concepts=wiki.concepts,
            methods=wiki.methods,
            limitations=wiki.limitations,
        )
        return ApiResponse(data=data, request_id=request.state.request_id)
    try:
        data = require_summary(paper_id)
    except KeyError:
        return _not_found(request, paper_id)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}/wiki", response_model=ApiResponse[WikiData], summary="读取数据库结构化结果")
def wiki(paper_id: int, request: Request, db: Session = Depends(db_session)):
    try:
        data = get_wiki(db, paper_id)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/qa", response_model=ApiResponse[AskPaperResult], summary="单论文问答")
def qa(paper_id: str, payload: AskPaperRequest, request: Request, db: Session = Depends(db_session)):
    if paper_id.isdigit():
        try:
            result = answer_question(db, int(paper_id), payload.question)
        except PaperServiceError as exc:
            return _db_error(request, exc)
        data = {
            "conversationId": result.conversation_id,
            "messageId": result.message_id,
            "paperId": str(result.paper_id),
            "answer": result.answer,
            "createdAt": result.created_at.isoformat(),
            "citations": result.citations,
            "historyCount": len(payload.history),
        }
        return ApiResponse(data=data, request_id=request.state.request_id)
    try:
        data = ask_paper(paper_id, payload)
    except KeyError:
        return _not_found(request, paper_id)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}", summary="获取论文详情")
def detail(paper_id: str, request: Request, db: Session = Depends(db_session)):
    if paper_id.isdigit():
        try:
            data = get_paper_detail(db, int(paper_id))
        except PaperServiceError as exc:
            return _db_error(request, exc)
        return ApiResponse(data=data, request_id=request.state.request_id)
    try:
        data = require_paper(paper_id)
    except KeyError:
        return _not_found(request, paper_id)
    return ApiResponse(data=data, request_id=request.state.request_id)
