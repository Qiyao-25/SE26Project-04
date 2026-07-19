from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import ensure_same_user, require_current_user
from app.core.database import get_db
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.schema.papers import PaperItem
from app.service.recommendations import daily_picks, profile_recommendations


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


@router.get("/daily", response_model=ApiResponse[list[PaperItem]], summary="读取每日论文推荐")
def daily(request: Request, limit: int = Query(default=3, ge=1, le=20), db: Session = Depends(db_session)):
    return ApiResponse(data=daily_picks(db, limit), request_id=request.state.request_id)


@router.get("/profile", response_model=ApiResponse[list[PaperItem]], summary="读取画像论文推荐")
def profile(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    persona: str | None = Query(default=None, max_length=32),
    topics: str | None = Query(default=None, max_length=1000),
    limit: int = Query(default=3, ge=1, le=20),
    exclude_ids: str | None = Query(default=None, max_length=500),
    current_user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    ensure_same_user(user_id, current_user)
    topic_values = [item.strip() for item in (topics or "").split(",") if item.strip()]
    excluded = [int(item) for item in (exclude_ids or "").split(",") if item.strip().isdigit()]
    return ApiResponse(
        data=profile_recommendations(
            db, user_id=user_id, persona=persona, topics=topic_values,
            limit=limit, exclude_ids=excluded,
        ),
        request_id=request.state.request_id,
    )
