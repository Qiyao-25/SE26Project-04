from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schema.common import ApiResponse
from app.schema.paper import PaperContent, PaperDetail, PaperSummary, SearchRequest, SearchResult
from app.schema.papers import BatchPaperRequest, BatchUpsertResponse, ParseRequest, PaperGraphData, PaperItem, PaperPage, PaperUpsert, ReadingAssistData, ReadingAssistRequest, SmartSearchRequest, SmartSearchResponse, TaskResponse, TextChunkBatch, WikiData
from app.schema.qa import AskPaperRequest, AskPaperResult
from app.service.paper import require_content, require_paper, require_summary, search_papers as search_mock_papers
from app.service.papers import PaperServiceError, answer_question, batch_upsert_papers, get_paper_detail, get_paper_graph, get_reading_assist, get_wiki, search_papers, smart_search_papers
from app.service.parse_agent_runner import run_parse_agent_job
from app.service.qa import ask_paper
from app.service.tasks import create_task

router = APIRouter(prefix="/api/papers", tags=["papers"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


def _not_found(request: Request, paper_id: str):
    return JSONResponse(status_code=404, content={"code": "PAPER_NOT_FOUND", "message": f"论文不存在：{paper_id}", "data": {}, "request_id": request.state.request_id})


def _db_error(request: Request, error: PaperServiceError):
    body = ApiResponse[dict](code=error.code, message=error.message, data={}, request_id=request.state.request_id)
    return JSONResponse(status_code=error.status_code, content=body.model_dump())


def _qa_payload(result, history_count: int) -> dict:
    return {
        "conversationId": result.conversation_id,
        "messageId": result.message_id,
        "paperId": str(result.paper_id),
        "answer": result.answer,
        "createdAt": result.created_at.isoformat(),
        "citations": [
            {**citation, "paperId": str(citation.get("paperId", result.paper_id))}
            for citation in result.citations
        ],
        "historyCount": history_count,
    }


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


@router.post("/smart-search", response_model=ApiResponse[SmartSearchResponse], summary="智能论文检索（查询改写+模糊匹配+生成回答）")
def smart_search(payload: SmartSearchRequest, request: Request, db: Session = Depends(db_session)):
    data = smart_search_papers(
        db,
        query=payload.query.strip(),
        page=payload.page,
        page_size=payload.page_size,
        category=payload.category,
        settings=request.app.state.settings,
    )
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/batch", response_model=ApiResponse[BatchUpsertResponse], summary="批量去重写入论文元数据")
def batch_papers(request: Request, payload: list[PaperUpsert] | BatchPaperRequest, db: Session = Depends(db_session)):
    try:
        items = payload if isinstance(payload, list) else payload.papers
        data = batch_upsert_papers(db, items)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/parse", response_model=ApiResponse[TaskResponse], summary="创建论文解析任务")
def parse(
    paper_id: int,
    payload: ParseRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(db_session),
):
    if not idempotency_key or not idempotency_key.strip():
        return _db_error(request, PaperServiceError("VALIDATION_ERROR", "必须提供 Idempotency-Key", 400))
    try:
        data, created = create_task(db, paper_id, payload.task_type, idempotency_key.strip(), force=payload.force)
    except ValueError as exc:
        if str(exc) == "PAPER_NOT_FOUND":
            return _db_error(request, PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404))
        return _db_error(request, PaperServiceError("TASK_CONFLICT", "解析任务状态或幂等键冲突", 409))

    settings = request.app.state.settings
    # 解析由当前 FastAPI 进程直接执行；无 LLM 配置时 runner 使用本地降级摘要。
    if data.status == "queued" and data.started_at is None:
        background_tasks.add_task(run_parse_agent_job, request.app.state.engine, data.task_id, settings)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/chunks", response_model=ApiResponse[dict], summary="批量写入论文文本块")
def chunks(paper_id: int, payload: TextChunkBatch, request: Request, db: Session = Depends(db_session)):
    from app.repository.chunks import upsert_chunks

    try:
        count = upsert_chunks(db, paper_id, payload)
    except ValueError as exc:
        if str(exc) == "PAPER_NOT_FOUND":
            return _db_error(request, PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404))
        raise
    return ApiResponse(data={"paper_id": paper_id, "upserted": count}, request_id=request.state.request_id)


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
        return ApiResponse(data=PaperContent(paperId=str(paper.paper_id), contentType="pdf+html", pdfUrl=paper.pdf_url, htmlUrl=f"https://ar5iv.labs.arxiv.org/html/{paper.arxiv_id}", defaultPage=1, sections=[]), request_id=request.state.request_id)
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
            experiments=wiki.experiments,
            limitations=wiki.limitations,
            validationFlags=wiki.validation_flags,
            chunkCount=wiki.chunk_count,
            qaReady=wiki.qa_ready,
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


@router.get("/{paper_id}/assist", response_model=ApiResponse[ReadingAssistData], summary="读取个性化辅助阅读")
def reading_assist_get(paper_id: int, request: Request, mode: str = Query(default="研究", max_length=16), db: Session = Depends(db_session)):
    try:
        data = get_reading_assist(db, paper_id, mode=mode, settings=request.app.state.settings)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}/graph", response_model=ApiResponse[PaperGraphData], summary="读取论文知识图谱")
def paper_graph(paper_id: int, request: Request, db: Session = Depends(db_session)):
    try:
        data = get_paper_graph(db, paper_id, settings=request.app.state.settings)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/graph", response_model=ApiResponse[PaperGraphData], summary="刷新论文知识图谱")
def rebuild_paper_graph(paper_id: int, request: Request, db: Session = Depends(db_session)):
    try:
        data = get_paper_graph(db, paper_id, settings=request.app.state.settings, force=True)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/assist", response_model=ApiResponse[ReadingAssistData], summary="生成个性化辅助阅读")
def reading_assist(paper_id: int, payload: ReadingAssistRequest, request: Request, db: Session = Depends(db_session)):
    try:
        data = get_reading_assist(db, paper_id, mode=payload.mode, force=payload.force, settings=request.app.state.settings)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/qa", response_model=ApiResponse[AskPaperResult], summary="单论文问答")
def qa(paper_id: str, payload: AskPaperRequest, request: Request, db: Session = Depends(db_session)):
    if paper_id.isdigit():
        try:
            result = answer_question(
                db,
                int(paper_id),
                payload.question,
                history=[item.model_dump() for item in payload.history],
                conversation_id=payload.conversationId,
                settings=request.app.state.settings,
            )
        except PaperServiceError as exc:
            return _db_error(request, exc)
        data = _qa_payload(result, len(payload.history))
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
