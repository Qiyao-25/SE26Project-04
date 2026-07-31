from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import ensure_same_user, require_current_user
from app.core.database import get_db
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.schema.papers import UserActionInput, UserActionItem, UserActionUpdate
from app.service.learning import create_action, delete_action, delete_actions_by_type, list_actions, list_public_comments, update_action

router = APIRouter(prefix="/api/learning/actions", tags=["learning"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


def error_response(request: Request, code: str, message: str, status_code: int):
    return JSONResponse(
        status_code=status_code,
        content=ApiResponse[dict](code=code, message=message, data={}, request_id=request.state.request_id).model_dump(),
    )


def map_error(request: Request, error: ValueError):
    mapping = {
        "VALIDATION_ERROR": ("VALIDATION_ERROR", "行为类型或请求参数不合法", 400),
        "PAPER_NOT_FOUND": ("PAPER_NOT_FOUND", "论文不存在", 404),
        "ACTION_NOT_FOUND": ("ACTION_NOT_FOUND", "用户行为不存在", 404),
        "ACTION_FORBIDDEN": ("ACTION_FORBIDDEN", "不能修改其他用户的行为", 403),
    }
    code, message, status_code = mapping.get(str(error), ("INTERNAL_ERROR", "学习行为处理失败", 500))
    return error_response(request, code, message, status_code)


@router.post("", response_model=ApiResponse[UserActionItem], summary="创建学习行为")
def action_create(payload: UserActionInput, request: Request, current_user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    ensure_same_user(payload.user_id, current_user)
    try:
        data, _created = create_action(db, payload)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/public-comments", response_model=ApiResponse[list[UserActionItem]], summary="读取论文公开评论")
def action_public_comments(
    request: Request,
    paper_id: int = Query(ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    _user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    try:
        data = list_public_comments(db, paper_id, limit=limit)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("", response_model=ApiResponse[list[UserActionItem]], summary="查询学习行为")
def action_list(
    user_id: str = Query(min_length=1, max_length=128),
    request: Request = None,
    paper_id: int | None = Query(default=None, ge=1),
    action_type: str | None = Query(default=None, max_length=64),
    current_user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    ensure_same_user(user_id, current_user)
    try:
        data = list_actions(db, user_id, paper_id, action_type)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.patch("/{action_id}", response_model=ApiResponse[UserActionItem], summary="修改学习行为")
def action_update(action_id: int, payload: UserActionUpdate, request: Request, current_user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    try:
        data = update_action(db, action_id, payload, user_id=current_user.user_id)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.delete("/bulk", response_model=ApiResponse[dict], summary="按类型批量删除学习行为")
def action_delete_bulk(
    request: Request,
    action_type: str = Query(min_length=1, max_length=64),
    user_id: str = Query(min_length=1, max_length=128),
    current_user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    ensure_same_user(user_id, current_user)
    try:
        deleted = delete_actions_by_type(db, user_id, action_type)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data={"deleted": deleted, "action_type": action_type}, request_id=request.state.request_id)


@router.delete("/{action_id}", response_model=ApiResponse[dict], summary="删除学习行为")
def action_delete(action_id: int, request: Request, current_user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    try:
        delete_action(db, action_id, user_id=current_user.user_id)
    except ValueError as exc:
        return map_error(request, exc)
    return ApiResponse(data={"deleted": True, "action_id": action_id}, request_id=request.state.request_id)
