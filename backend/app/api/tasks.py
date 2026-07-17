from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schema.common import ApiResponse
from app.schema.papers import StructuredResultBatch, TaskResponse, TaskUpdate
from app.service.tasks import create_task, get_task, list_tasks, save_results, update_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


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
    }
    code, message, status_code = mapping.get(str(error), ("INTERNAL_ERROR", "任务处理失败", 500))
    return error_response(request, code, message, status_code)


@router.get("/{task_id}", response_model=ApiResponse[TaskResponse], summary="查询解析任务")
def task_detail(task_id: int, request: Request, db: Session = Depends(db_session)):
    try:
        data = get_task(db, task_id)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("", response_model=ApiResponse[list[TaskResponse]], summary="查询解析任务队列")
def task_list(
    request: Request,
    db: Session = Depends(db_session),
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
):
    try:
        data = list_tasks(db, status=status, limit=limit)
    except ValueError as exc:
        return error_response(request, "VALIDATION_ERROR", str(exc), 400)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.patch("/{task_id}", response_model=ApiResponse[TaskResponse], summary="更新解析任务状态")
def task_update(task_id: int, payload: TaskUpdate, request: Request, db: Session = Depends(db_session)):
    try:
        data = update_task(db, task_id, payload)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/{task_id}/results", response_model=ApiResponse[TaskResponse], summary="写入结构化解析结果")
def task_results(task_id: int, payload: StructuredResultBatch, request: Request, db: Session = Depends(db_session)):
    try:
        data = save_results(db, task_id, payload)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)
