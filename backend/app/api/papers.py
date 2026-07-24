from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.core.auth import require_admin, require_current_user, db_session
from app.agents.llm_client import LlmError
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.schema.paper import PaperContent, PaperDetail, PaperSummary, SearchRequest, SearchResult
from app.schema.papers import BatchPaperRequest, BatchUpsertResponse, FetchOnePaperRequest, FetchOnePaperResponse, ParseRequest, PaperCompareRequest, PaperCompareResponse, PaperGraphData, PaperItem, PaperPage, PaperUpsert, ReadingAssistData, ReadingAssistRequest, SmartSearchRequest, SmartSearchResponse, TaskResponse, TextChunkBatch, WikiData
from app.schema.qa import AskPaperRequest, AskPaperResult
from app.service.paper import require_content, require_paper, require_summary, search_papers as search_mock_papers
from app.service.papers import PaperServiceError, answer_question, batch_upsert_papers, compare_papers, delete_paper, fetch_one_paper, get_paper_detail, get_paper_graph, get_reading_assist, get_wiki, search_papers, smart_search_papers
from app.service.parse_agent_runner import run_parse_agent_job
from app.service.pdf_stream import load_paper_pdf_bytes, pdf_response
from app.service.qa import ask_paper
from app.service.tasks import create_task

router = APIRouter(prefix="/api/papers", tags=["papers"])


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
        "answerMode": getattr(result, "answer_mode", None) or "agent",
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
    topic: str | None = Query(default=None, max_length=64, description="主题大类，如 cs / stat / math"),
    published_from: datetime | None = None,
    published_to: datetime | None = None,
    sort_by: str = Query(
        default="published_desc",
        description="排序：published_*|created_*|title_*|id_*|author_*|topic_*|category_*|arxiv_*|status_*|relevance",
    ),
    search_field: str = Query(
        default="all",
        description="Wiki/字段检索：all|title|author|keyword|direction|concept",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
):
    data = search_papers(
        db,
        keyword=keyword,
        author=author,
        category=category,
        topic=topic,
        published_from=published_from,
        published_to=published_to,
        sort_by=sort_by,
        search_field=search_field,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/smart-search", response_model=ApiResponse[SmartSearchResponse], summary="智能论文检索（查询改写+模糊匹配+生成回答）")
def smart_search(payload: SmartSearchRequest, request: Request, _user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    data = smart_search_papers(
        db,
        query=payload.query.strip(),
        page=payload.page,
        page_size=payload.page_size,
        category=payload.category,
        rewritten_query=payload.rewritten_query,
        keywords=payload.keywords,
        category_hints=payload.category_hints,
        author_hints=payload.author_hints,
        search_mode=payload.search_mode,
        search_session_id=payload.search_session_id,
        include_answer=payload.include_answer,
        settings=request.app.state.settings,
    )
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/fetch-one", response_model=ApiResponse[FetchOnePaperResponse], summary="按 arXiv 编号或标题抓取单篇论文入库")
def fetch_one(
    payload: FetchOnePaperRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(db_session),
    _user: AuthUser = Depends(require_current_user),
):
    try:
        data = fetch_one_paper(
            db,
            query=payload.query.strip(),
            parse=payload.parse,
            settings=request.app.state.settings,
        )
    except PaperServiceError as exc:
        return _db_error(request, exc)

    task = data.task
    if task is not None and task.status == "queued" and task.started_at is None:
        background_tasks.add_task(run_parse_agent_job, request.app.state.engine, task.task_id, request.app.state.settings)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/batch", response_model=ApiResponse[BatchUpsertResponse], summary="批量去重写入论文元数据")
def batch_papers(
    request: Request,
    payload: list[PaperUpsert] | BatchPaperRequest,
    db: Session = Depends(db_session),
    _admin: AuthUser = Depends(require_admin),
):
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
    _user: AuthUser = Depends(require_current_user),
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
def chunks(
    paper_id: int,
    payload: TextChunkBatch,
    request: Request,
    db: Session = Depends(db_session),
    _admin: AuthUser = Depends(require_admin),
):
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


@router.get("/{paper_id}/pdf", summary="代理论文 PDF（同源可划词阅读）", response_class=Response)
def paper_pdf(
    paper_id: int,
    request: Request,
    db: Session = Depends(db_session),
    _user: AuthUser = Depends(require_current_user),
):
    try:
        data, _content_type = load_paper_pdf_bytes(db, paper_id)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return pdf_response(data, filename=f"paper-{paper_id}.pdf")


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
            validationLabels=wiki.validation_labels,
            uncertainFields=wiki.uncertain_fields,
            chunkCount=wiki.chunk_count,
            qaReady=wiki.qa_ready,
        )
        return ApiResponse(data=data, request_id=request.state.request_id)
    try:
        data = require_summary(paper_id)
    except KeyError:
        return _not_found(request, paper_id)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/compare", response_model=ApiResponse[PaperCompareResponse], summary="生成两篇论文的智能对比总结")
def compare_paper(
    paper_id: int,
    payload: PaperCompareRequest,
    request: Request,
    _user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    try:
        data = compare_papers(
            db,
            paper_id=paper_id,
            other_paper_id=payload.other_paper_id,
            settings=request.app.state.settings,
        )
    except PaperServiceError as exc:
        return _db_error(request, exc)
    except LlmError as exc:
        body = ApiResponse[dict](code="LLM_ERROR", message=str(exc), data={}, request_id=request.state.request_id)
        return JSONResponse(status_code=502, content=body.model_dump())
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}/wiki", response_model=ApiResponse[WikiData], summary="读取数据库结构化结果")
def wiki(paper_id: int, request: Request, db: Session = Depends(db_session)):
    try:
        data = get_wiki(db, paper_id)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}/chunks", response_model=ApiResponse[list[dict]], summary="读取论文段落块（供段落笔记）")
def paper_chunks(
    paper_id: int,
    request: Request,
    limit: int = Query(default=40, ge=1, le=120),
    _user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    from app.model import Paper
    from app.repository.chunks import list_chunks_for_paper
    from app.repository.papers import get_paper

    paper = get_paper(db, paper_id)
    if paper is None:
        return _db_error(request, PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404))
    return ApiResponse(data=list_chunks_for_paper(db, paper_id, limit=limit), request_id=request.state.request_id)


@router.get("/{paper_id}/assist", response_model=ApiResponse[ReadingAssistData], summary="读取个性化辅助阅读")
def reading_assist_get(paper_id: int, request: Request, mode: str = Query(default="研究", max_length=16), _user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    try:
        data = get_reading_assist(db, paper_id, mode=mode, settings=request.app.state.settings)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{paper_id}/graph", response_model=ApiResponse[PaperGraphData], summary="读取论文知识图谱")
def paper_graph(paper_id: int, request: Request, force: bool = Query(default=False), _user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    try:
        data = get_paper_graph(db, paper_id, settings=request.app.state.settings, force=force)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/graph", response_model=ApiResponse[PaperGraphData], summary="刷新论文知识图谱")
def rebuild_paper_graph(paper_id: int, request: Request, _user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    try:
        data = get_paper_graph(db, paper_id, settings=request.app.state.settings, force=True)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/assist", response_model=ApiResponse[ReadingAssistData], summary="生成个性化辅助阅读")
def reading_assist(paper_id: int, payload: ReadingAssistRequest, request: Request, _user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    try:
        data = get_reading_assist(db, paper_id, mode=payload.mode, force=payload.force, settings=request.app.state.settings)
    except PaperServiceError as exc:
        return _db_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{paper_id}/qa", response_model=ApiResponse[AskPaperResult], summary="单论文问答")
def qa(paper_id: str, payload: AskPaperRequest, request: Request, _user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
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
    except LlmError as exc:
        message = str(exc)
        code = "QA_AGENT_UNAVAILABLE" if "未配置" in message or "未启用" in message else "QA_AGENT_FAILED"
        status_code = 503 if code == "QA_AGENT_UNAVAILABLE" else 502
        return JSONResponse(
            status_code=status_code,
            content=ApiResponse[dict](code=code, message=message, data={}, request_id=request.state.request_id).model_dump(),
        )
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.delete("/{paper_id}", response_model=ApiResponse[PaperItem], summary="软删除论文（管理员）")
def remove_paper(
    paper_id: int,
    request: Request,
    db: Session = Depends(db_session),
    _admin: AuthUser = Depends(require_admin),
):
    try:
        data = delete_paper(db, paper_id)
    except PaperServiceError as exc:
        return _db_error(request, exc)
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
