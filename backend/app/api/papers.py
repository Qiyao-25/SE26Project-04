from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schema.common import ApiResponse
from app.schema.papers import BatchUpsertResponse, PaperItem, PaperPage, PaperUpsert, QaRequest, QaResponse, WikiData
from app.service.papers import PaperServiceError, answer_question, batch_upsert_papers, get_paper_detail, get_wiki, search_papers

router = APIRouter(prefix="/papers", tags=["papers"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


@router.get("", response_model=ApiResponse[PaperPage], summary="检索论文元数据")
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
        from fastapi.responses import JSONResponse

        body = ApiResponse[dict](code=exc.code, message=exc.message, data={}, request_id=request.state.request_id)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}", response_model=ApiResponse[PaperItem], summary="读取论文详情")
def paper_detail(request: Request, paper_id: int, db: Session = Depends(db_session)):
    try:
        data = get_paper_detail(db, paper_id)
    except PaperServiceError as exc:
        from fastapi.responses import JSONResponse

        body = ApiResponse[dict](code=exc.code, message=exc.message, data={}, request_id=request.state.request_id)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}/wiki", response_model=ApiResponse[WikiData], summary="读取论文结构化结果")
def paper_wiki(request: Request, paper_id: int, db: Session = Depends(db_session)):
    try:
        data = get_wiki(db, paper_id)
    except PaperServiceError as exc:
        from fastapi.responses import JSONResponse

        body = ApiResponse[dict](code=exc.code, message=exc.message, data={}, request_id=request.state.request_id)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/qa", response_model=ApiResponse[QaResponse], summary="论文范围内的最小问答闭环")
def paper_qa(request: Request, paper_id: int, payload: QaRequest, db: Session = Depends(db_session)):
    try:
        data = answer_question(db, paper_id, payload.question)
    except PaperServiceError as exc:
        from fastapi.responses import JSONResponse

        body = ApiResponse[dict](code=exc.code, message=exc.message, data={}, request_id=request.state.request_id)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())
    return ApiResponse(data=data, request_id=request.state.request_id)
