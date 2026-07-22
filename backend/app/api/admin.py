from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.auth import require_admin
from app.core.database import get_db
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.service.admin import admin_audit, admin_overview, admin_quality, admin_tasks, admin_users, delete_user, update_user_status
from app.service.runtime_settings import apply_runtime_settings, update_crawl_settings


router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserStatusUpdate(BaseModel):
    is_active: bool


class CrawlSettingsUpdate(BaseModel):
    crawl_enabled: bool | None = None
    crawl_interval_s: int | None = Field(default=None, ge=60, le=7 * 24 * 3600)


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


@router.get("/overview", response_model=ApiResponse[dict], summary="读取管理员概览")
def overview(request: Request, _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    return ApiResponse(data=admin_overview(db, request.app.state.settings), request_id=request.state.request_id)


@router.get("/tasks", response_model=ApiResponse[list[dict]], summary="读取真实解析任务")
def tasks(request: Request, limit: int = Query(default=50, ge=1, le=100), _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    return ApiResponse(data=admin_tasks(db, limit), request_id=request.state.request_id)


@router.get("/users", response_model=ApiResponse[list[dict]], summary="读取管理员用户列表")
def users(request: Request, limit: int = Query(default=100, ge=1, le=200), _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    return ApiResponse(data=admin_users(db, limit), request_id=request.state.request_id)


@router.patch("/users/{user_id}", response_model=ApiResponse[dict], summary="修改用户启用状态")
def user_status(user_id: int, payload: UserStatusUpdate, request: Request, _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    try:
        data = update_user_status(db, user_id, payload.is_active)
    except ValueError as exc:
        code = str(exc)
        if code == "USER_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content=ApiResponse[dict](
                    code="USER_NOT_FOUND",
                    message="用户不存在",
                    data={},
                    request_id=request.state.request_id,
                ).model_dump(),
            )
        if code == "ADMIN_CANNOT_DISABLE":
            return JSONResponse(
                status_code=400,
                content=ApiResponse[dict](
                    code="ADMIN_CANNOT_DISABLE",
                    message="管理员账户不可禁用",
                    data={},
                    request_id=request.state.request_id,
                ).model_dump(),
            )
        raise
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.delete("/users/{user_id}", response_model=ApiResponse[dict], summary="删除用户")
def user_delete(user_id: int, request: Request, _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    try:
        data = delete_user(db, user_id)
    except ValueError as exc:
        code = str(exc)
        if code == "USER_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content=ApiResponse[dict](
                    code="USER_NOT_FOUND",
                    message="用户不存在",
                    data={},
                    request_id=request.state.request_id,
                ).model_dump(),
            )
        if code == "ADMIN_CANNOT_DELETE":
            return JSONResponse(
                status_code=400,
                content=ApiResponse[dict](
                    code="ADMIN_CANNOT_DELETE",
                    message="管理员账户不可删除",
                    data={},
                    request_id=request.state.request_id,
                ).model_dump(),
            )
        raise
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/crawl-settings", response_model=ApiResponse[dict], summary="读取自动抓取调度设置")
def crawl_settings_get(request: Request, _admin: AuthUser = Depends(require_admin)):
    data = apply_runtime_settings(request.app.state.settings)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.patch("/crawl-settings", response_model=ApiResponse[dict], summary="更新自动抓取调度设置")
def crawl_settings_patch(payload: CrawlSettingsUpdate, request: Request, _admin: AuthUser = Depends(require_admin)):
    data = update_crawl_settings(
        request.app.state.settings,
        crawl_enabled=payload.crawl_enabled,
        crawl_interval_s=payload.crawl_interval_s,
    )
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/quality", response_model=ApiResponse[dict], summary="读取解析质量统计")
def quality(request: Request, limit: int = Query(default=50, ge=1, le=100), _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    return ApiResponse(data=admin_quality(db, limit), request_id=request.state.request_id)


@router.get("/audit", response_model=ApiResponse[list[dict]], summary="读取管理员审计记录")
def audit(request: Request, limit: int = Query(default=50, ge=1, le=100), _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    return ApiResponse(data=admin_audit(db, limit), request_id=request.state.request_id)
