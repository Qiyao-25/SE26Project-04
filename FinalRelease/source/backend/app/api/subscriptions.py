from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import ensure_same_user, require_current_user
from app.core.database import get_db
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.schema.papers import SubscriptionItem, SubscriptionSaveRequest, SubscriptionSyncResult
from app.service.subscriptions import list_subscriptions, save_subscriptions, sync_subscriptions


router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


@router.get("", response_model=ApiResponse[list[SubscriptionItem]], summary="读取用户订阅列表")
def get_subscriptions(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    current_user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    ensure_same_user(user_id, current_user)
    return ApiResponse(data=list_subscriptions(db, user_id), request_id=request.state.request_id)


@router.put("", response_model=ApiResponse[list[SubscriptionItem]], summary="保存用户订阅列表")
def put_subscriptions(
    payload: SubscriptionSaveRequest,
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    current_user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    ensure_same_user(user_id, current_user)
    items = [item.model_dump() for item in payload.subscriptions]
    return ApiResponse(data=save_subscriptions(db, user_id, items), request_id=request.state.request_id)


@router.post("/sync", response_model=ApiResponse[SubscriptionSyncResult], summary="立即从 arXiv 同步订阅论文")
def sync_now(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    max_per_subscription: int = Query(default=5, ge=1, le=20),
    current_user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    ensure_same_user(user_id, current_user)
    result = sync_subscriptions(
        db,
        user_id,
        max_per_subscription=max_per_subscription,
        settings=request.app.state.settings,
    )
    return ApiResponse(data=result, request_id=request.state.request_id)
