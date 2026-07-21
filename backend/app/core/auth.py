import secrets

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schema.auth import AuthUser
from app.service.auth import user_from_token


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


def require_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> AuthUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return user_from_token(db, token, request.app.state.settings)
    except ValueError:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")


def require_admin(current_user: AuthUser = Depends(require_current_user)) -> AuthUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def ensure_same_user(requested_user_id: str, current_user: AuthUser) -> None:
    if requested_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="不能访问其他用户的数据")


def require_worker_access(
    request: Request,
    worker_token: str | None = Header(default=None, alias="X-Worker-Token"),
) -> None:
    _verify_worker_token(request, worker_token)


def _verify_worker_token(request: Request, worker_token: str | None) -> None:
    settings = request.app.state.settings
    expected = settings.worker_token.strip()
    # Local development keeps the pipeline easy to run. Production must configure it.
    if settings.environment == "dev" and (not expected or expected.startswith("replace-with-")):
        return
    if not expected or not worker_token or not secrets.compare_digest(worker_token, expected):
        raise HTTPException(status_code=403, detail="Worker 内部接口未授权")
