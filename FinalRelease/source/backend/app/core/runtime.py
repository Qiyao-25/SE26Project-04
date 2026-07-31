"""Process uptime helpers for admin overview / health."""

from __future__ import annotations

from datetime import datetime, timezone

_PROCESS_STARTED_AT: datetime | None = None


def mark_process_started(at: datetime | None = None) -> datetime:
    global _PROCESS_STARTED_AT
    _PROCESS_STARTED_AT = at or datetime.now(timezone.utc)
    return _PROCESS_STARTED_AT


def process_started_at() -> datetime | None:
    return _PROCESS_STARTED_AT


def uptime_seconds(started_at: datetime | None = None) -> int:
    start = started_at or _PROCESS_STARTED_AT
    if start is None:
        return 0
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - start).total_seconds()))


def format_uptime(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}天")
    if hours or days:
        parts.append(f"{hours}小时")
    if minutes or not parts:
        parts.append(f"{minutes}分")
    if not days and not hours and seconds < 60:
        parts = [f"{secs}秒"]
    return "".join(parts)
