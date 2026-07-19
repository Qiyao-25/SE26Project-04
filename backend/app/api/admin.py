from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.database import get_db
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.service.admin import admin_audit, admin_quality, admin_tasks, admin_users


router = APIRouter(prefix="/api/admin", tags=["admin"])


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


@router.get("/quality", response_model=ApiResponse[dict], summary="读取解析质量统计")
def quality(request: Request, limit: int = Query(default=50, ge=1, le=100), _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    return ApiResponse(data=admin_quality(db, limit), request_id=request.state.request_id)


@router.get("/audit", response_model=ApiResponse[list[dict]], summary="读取管理员审计记录")
def audit(request: Request, limit: int = Query(default=50, ge=1, le=100), _admin: AuthUser = Depends(require_admin), db: Session = Depends(db_session)):
    return ApiResponse(data=admin_audit(db, limit), request_id=request.state.request_id)
