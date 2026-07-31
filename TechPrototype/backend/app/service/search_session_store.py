"""In-memory smart-search session store for stable pagination."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


_TTL_S = 20 * 60
_MAX_SESSIONS = 500
_lock = threading.Lock()
_SESSIONS: dict[str, "SearchSession"] = {}


@dataclass
class SearchSession:
    session_id: str
    query: str
    plan: dict[str, Any]
    paper_ids: list[int]
    category: str | None = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def alive(self) -> bool:
        return time.time() < self.expires_at


def create_search_session(
    *,
    query: str,
    plan: dict[str, Any],
    paper_ids: list[int],
    category: str | None = None,
    ttl_s: int = _TTL_S,
) -> SearchSession:
    now = time.time()
    session_id = f"ss-{uuid.uuid4().hex[:16]}"
    item = SearchSession(
        session_id=session_id,
        query=query,
        plan=plan,
        paper_ids=list(paper_ids),
        category=category,
        created_at=now,
        expires_at=now + ttl_s,
    )
    with _lock:
        _purge_locked(now)
        if len(_SESSIONS) >= _MAX_SESSIONS:
            # Drop oldest
            oldest = sorted(_SESSIONS.values(), key=lambda s: s.created_at)[: max(1, len(_SESSIONS) // 10)]
            for old in oldest:
                _SESSIONS.pop(old.session_id, None)
        _SESSIONS[session_id] = item
    return item


def get_search_session(session_id: str | None) -> SearchSession | None:
    if not session_id:
        return None
    with _lock:
        _purge_locked(time.time())
        item = _SESSIONS.get(session_id)
        if item is None or not item.alive():
            _SESSIONS.pop(session_id or "", None)
            return None
        return item


def _purge_locked(now: float) -> None:
    dead = [key for key, value in _SESSIONS.items() if value.expires_at <= now]
    for key in dead:
        _SESSIONS.pop(key, None)


__all__ = ["SearchSession", "create_search_session", "get_search_session"]
