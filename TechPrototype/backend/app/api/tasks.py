from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import db_session, require_admin, require_current_user, require_worker_access
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.schema.papers import ParseResultCommit, StructuredResultBatch, TaskClaimRequest, TaskQueueStats, TaskResponse, TaskUpdate
from app.service.tasks import claim_task, create_task, delete_task, enqueue_pending_tasks, get_task, list_tasks, queue_stats, recover_stale_tasks, retry_task, save_parse_result, save_results, update_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def error_response(request: Request, code: str, message: str, status_code: int):
    return JSONResponse(
        status_code=status_code,
        content=ApiResponse[dict](code=code, message=message, data={}, request_id=request.state.request_id).model_dump(),
    )


def map_error(request: Request, error: ValueError):
    mapping = {
        "PAPER_NOT_FOUND": ("PAPER_NOT_FOUND", "论文不存在", 404),
        "TASK_NOT_FOUND": ("TASK_NOT_FOUND", "解析任务不存在", 404),
        "TASK_CONFLICT": ("TASK_CONFLICT", "解析任务状态或幂等键冲突", 409),
        "TASK_RETRY_CONFLICT": ("TASK_RETRY_CONFLICT", "当前任务状态不允许重试", 409),
        "TASK_RETRY_EXHAUSTED": ("TASK_RETRY_EXHAUSTED", "解析任务已达到最大重试次数", 409),
        "TASK_STATE_CONFLICT": ("TASK_STATE_CONFLICT", "解析任务状态不允许该操作", 409),
        "TASK_DELETE_CONFLICT": ("TASK_DELETE_CONFLICT", "运行中的解析任务不可删除", 409),
        "WORKER_ID_INVALID": ("WORKER_ID_INVALID", "Worker 标识不能为空", 400),
    }
    code, message, status_code = mapping.get(str(error), ("INTERNAL_ERROR", "任务处理失败", 500))
    return error_response(request, code, message, status_code)


@router.get("/stats", response_model=ApiResponse[TaskQueueStats], summary="查询解析队列统计")
def task_stats(
    request: Request,
    _admin: AuthUser = Depends(require_admin),
    db: Session = Depends(db_session),
    timeout_seconds: int = Query(default=900, ge=60, le=86400),
):
    return ApiResponse(
        data=queue_stats(db, timeout_seconds),
        request_id=request.state.request_id,
    )


@router.post("/claim", response_model=ApiResponse[TaskResponse | None], summary="Worker 原子领取解析任务")
def task_claim(
    payload: TaskClaimRequest,
    request: Request,
    _worker: None = Depends(require_worker_access),
    db: Session = Depends(db_session),
):
    data = claim_task(db, payload.worker_id)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/{task_id}", response_model=ApiResponse[TaskResponse], summary="查询解析任务")
def task_detail(
    task_id: int,
    request: Request,
    db: Session = Depends(db_session),
    _user: AuthUser = Depends(require_current_user),
):
    try:
        data = get_task(db, task_id)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("", response_model=ApiResponse[list[TaskResponse]], summary="查询解析任务队列")
def task_list(
    request: Request,
    _admin: AuthUser = Depends(require_admin),
    db: Session = Depends(db_session),
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
):
    try:
        data = list_tasks(db, status=status, limit=limit)
    except ValueError as exc:
        return error_response(request, "VALIDATION_ERROR", str(exc), 400)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/recover-stale", response_model=ApiResponse[dict], summary="恢复超时解析任务")
def recover_stale(
    request: Request,
    _admin: AuthUser = Depends(require_admin),
    db: Session = Depends(db_session),
    timeout_seconds: int = Query(default=900, ge=60, le=86400),
):
    tasks = recover_stale_tasks(db, timeout_seconds)
    return ApiResponse(
        data={"recovered": len(tasks), "tasks": tasks},
        request_id=request.state.request_id,
    )


@router.post("/enqueue-pending", response_model=ApiResponse[dict], summary="将待解析论文加入队列")
def enqueue_pending(
    request: Request,
    db: Session = Depends(db_session),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: AuthUser = Depends(require_admin),
):
    tasks = enqueue_pending_tasks(db, limit)
    return ApiResponse(
        data={"queued": len(tasks), "tasks": tasks},
        request_id=request.state.request_id,
    )


@router.patch("/{task_id}", response_model=ApiResponse[TaskResponse], summary="更新解析任务状态")
def task_update(task_id: int, payload: TaskUpdate, request: Request, _worker: None = Depends(require_worker_access), db: Session = Depends(db_session)):
    try:
        data = update_task(db, task_id, payload)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{task_id}/retry", response_model=ApiResponse[TaskResponse], summary="重试失败解析任务")
def task_retry(
    task_id: int,
    request: Request,
    db: Session = Depends(db_session),
    _admin: AuthUser = Depends(require_admin),
):
    try:
        data = retry_task(db, task_id)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.delete("/{task_id}", response_model=ApiResponse[dict], summary="删除解析任务")
def task_delete(
    task_id: int,
    request: Request,
    db: Session = Depends(db_session),
    _admin: AuthUser = Depends(require_admin),
):
    try:
        data = delete_task(db, task_id)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{task_id}/results", response_model=ApiResponse[TaskResponse], summary="写入结构化解析结果")
def task_results(task_id: int, payload: StructuredResultBatch, request: Request, _worker: None = Depends(require_worker_access), db: Session = Depends(db_session)):
    try:
        data = save_results(db, task_id, payload)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{task_id}/finalize", response_model=ApiResponse[TaskResponse], summary="一次性提交论文解析结果")
def task_finalize(task_id: int, payload: ParseResultCommit, request: Request, _worker: None = Depends(require_worker_access), db: Session = Depends(db_session)):
    try:
        data = save_parse_result(db, task_id, payload)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)
