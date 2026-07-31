from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schema.auth import AccountUpdate, AuthResponse, AuthUser, LoginRequest, RegisterRequest
from app.schema.common import ApiResponse
from app.service.auth import login, register, update_account, user_from_token


router = APIRouter(prefix="/api/auth", tags=["auth"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


def _error(request: Request, code: str, message: str, status: int):
    return JSONResponse(status_code=status, content=ApiResponse[dict](code=code, message=message, data={}, request_id=request.state.request_id).model_dump())


@router.post("/register", response_model=ApiResponse[AuthResponse], summary="用户注册")
def auth_register(payload: RegisterRequest, request: Request, db: Session = Depends(db_session)):
    try:
        data = register(db, payload, request.app.state.settings)
    except ValueError as exc:
        code = str(exc)
        return _error(request, code, "邮箱已注册" if code == "EMAIL_EXISTS" else "邮箱格式不正确", 409 if code == "EMAIL_EXISTS" else 400)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.post("/login", response_model=ApiResponse[AuthResponse], summary="用户登录")
def auth_login(payload: LoginRequest, request: Request, db: Session = Depends(db_session)):
    try:
        data = login(db, payload, request.app.state.settings)
    except ValueError:
        return _error(request, "AUTH_INVALID", "账号或密码错误", 401)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/me", response_model=ApiResponse[AuthUser], summary="读取当前用户")
def auth_me(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    if not authorization or not authorization.lower().startswith("bearer "):
        return _error(request, "AUTH_REQUIRED", "请先登录", 401)
    try:
        user = user_from_token(db, authorization.split(" ", 1)[1].strip(), request.app.state.settings)
    except ValueError:
        return _error(request, "AUTH_INVALID", "登录已失效，请重新登录", 401)
    return ApiResponse(data=user, request_id=request.state.request_id)


@router.put("/account", response_model=ApiResponse[AuthResponse], summary="修改账户信息")
def account_update(payload: AccountUpdate, request: Request, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    if not authorization or not authorization.lower().startswith("bearer "):
        return _error(request, "AUTH_REQUIRED", "请先登录", 401)
    try:
        user = user_from_token(db, authorization.split(" ", 1)[1].strip(), request.app.state.settings)
        data = update_account(db, user.user_id, payload, request.app.state.settings)
    except ValueError as exc:
        code = str(exc)
        messages = {"AUTH_INVALID": "登录已失效，请重新登录", "PASSWORD_INVALID": "当前密码错误", "EMAIL_EXISTS": "邮箱已注册"}
        return _error(request, code, messages.get(code, "账户信息不合法"), 401 if code == "AUTH_INVALID" else 400)
    return ApiResponse(data=data, request_id=request.state.request_id)
