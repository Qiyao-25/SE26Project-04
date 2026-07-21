"""DEBUG ONLY: manual trigger for the scheduled crawl tick.

Remove this entire file and its registration in app.main to drop the debug API.
Gate: PAPERMATE_ENABLE_CRAWL_DEBUG=true
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import db_session, require_current_user
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.service.subscriptions import sync_all_users

logger = logging.getLogger("papermate.debug_crawl")

# Tag makes it easy to find in OpenAPI when docs are enabled.
router = APIRouter(prefix="/api/debug/crawl", tags=["debug-crawl-REMOVE-ME"])


@router.post("/run", response_model=ApiResponse[dict], summary="[DEBUG] 手动执行一轮全站订阅抓取")
def run_crawl_tick(
    request: Request,
    max_per_subscription: int = Query(default=3, ge=1, le=20),
    _user: AuthUser = Depends(require_current_user),
    db: Session = Depends(db_session),
):
    settings = request.app.state.settings
    if not getattr(settings, "enable_crawl_debug", False):
        raise HTTPException(status_code=404, detail="调试接口未启用")

    stats = sync_all_users(db, max_per_subscription=max_per_subscription)
    logger.info("debug_crawl_run user=%s stats=%s", _user.user_id, stats)
    return ApiResponse(
        data={
            "ok": True,
            "trigger": "manual_debug",
            "stats": stats,
            "note": "与定时调度器同一逻辑（sync_all_users）；正式环境请关闭 PAPERMATE_ENABLE_CRAWL_DEBUG",
        },
        request_id=request.state.request_id,
    )
