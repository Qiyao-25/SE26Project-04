"""Subscription preferences + arXiv sync for personalized feeds."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.schema.papers import AuthorInput, PaperUpsert, SubscriptionItem, SubscriptionSyncResult
from app.service.arxiv_client import ArxivClient
from app.service.papers import batch_upsert_papers
from app.service.profile import get_profile, patch_profile_preferences

logger = logging.getLogger("papermate.subscriptions")


def normalize_subscriptions(raw: list | None) -> list[dict]:
    items: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in raw or []:
        if not isinstance(row, dict):
            continue
        stype = str(row.get("type") or "").strip().lower()
        value = str(row.get("value") or "").strip()
        if stype not in {"keyword", "category"} or not value:
            continue
        key = (stype, value.casefold())
        if key in seen:
            continue
        seen.add(key)
        enabled = row.get("enabled", True)
        items.append(
            {
                "key": str(row.get("key") or row.get("id") or uuid.uuid4().hex[:8]),
                "type": stype,
                "value": value,
                "enabled": bool(enabled),
            }
        )
        if len(items) >= 30:
            break
    return items


def list_subscriptions(session: Session, user_id: str) -> list[SubscriptionItem]:
    profile = get_profile(session, user_id)
    prefs = dict(profile.preferences or {})
    return [SubscriptionItem(**item) for item in normalize_subscriptions(prefs.get("subscriptions"))]


def save_subscriptions(session: Session, user_id: str, subscriptions: list[dict]) -> list[SubscriptionItem]:
    normalized = normalize_subscriptions(subscriptions)
    patch_profile_preferences(
        session,
        user_id,
        {
            "subscriptions": normalized,
        },
    )
    return [SubscriptionItem(**item) for item in normalized]


def _build_query(item: dict) -> str:
    if item["type"] == "category":
        return f"cat:{item['value']}"
    return f'all:"{item["value"]}"'


def _parse_published(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def sync_subscriptions(
    session: Session,
    user_id: str,
    *,
    max_per_subscription: int = 5,
    client: ArxivClient | None = None,
) -> SubscriptionSyncResult:
    profile = get_profile(session, user_id)
    prefs = dict(profile.preferences or {})
    subscriptions = normalize_subscriptions(prefs.get("subscriptions"))
    enabled = [item for item in subscriptions if item.get("enabled", True)]
    if not enabled:
        return SubscriptionSyncResult(
            user_id=user_id,
            fetched=0,
            created=0,
            updated=0,
            paper_ids=[],
            message="没有启用中的订阅，请先在设置页添加关键词或分类",
            synced_at=datetime.now(timezone.utc),
        )

    client = client or ArxivClient(min_interval_s=3.0)
    payloads: list[PaperUpsert] = []
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    errors: list[str] = []
    skipped_dupes = 0

    from app.service.dedupe import normalize_title
    from app.model import Paper
    from sqlalchemy import select

    existing_by_title: dict[str, int] = {}
    for paper in session.scalars(select(Paper).where(Paper.deleted_at.is_(None))).all():
        key = normalize_title(paper.title or "")
        if key and key not in existing_by_title:
            existing_by_title[key] = paper.id

    reused_ids: list[int] = []

    for item in enabled:
        query = _build_query(item)
        try:
            metas = client.search(search_query=query, max_results=max_per_subscription)
        except Exception as exc:  # noqa: BLE001
            logger.warning("subscription_fetch_failed user=%s query=%s err=%s", user_id, query, exc)
            errors.append(f"{item['type']}:{item['value']} -> {exc}")
            continue
        for meta in metas:
            if meta.arxiv_id in seen_ids:
                skipped_dupes += 1
                continue
            title_key = normalize_title(meta.title or "")
            if title_key and title_key in seen_titles:
                skipped_dupes += 1
                continue
            if title_key and title_key in existing_by_title:
                skipped_dupes += 1
                reused_ids.append(existing_by_title[title_key])
                seen_titles.add(title_key)
                continue
            seen_ids.add(meta.arxiv_id)
            if title_key:
                seen_titles.add(title_key)
            payloads.append(
                PaperUpsert(
                    arxiv_id=meta.arxiv_id,
                    title=meta.title or meta.arxiv_id,
                    authors=[AuthorInput(name=name) for name in meta.authors[:20]],
                    abstract=meta.abstract,
                    published_at=_parse_published(meta.published),
                    primary_category=(meta.categories[0] if meta.categories else None),
                    pdf_url=meta.pdf_url,
                    source_url=meta.abs_url,
                    ingest_status="metadata_only",
                )
            )

    created = updated = 0
    paper_ids: list[int] = []
    if payloads:
        result = batch_upsert_papers(session, payloads)
        created = result.created
        updated = result.updated
        paper_ids = [item.paper_id for item in result.items]

    paper_ids = list(dict.fromkeys([*paper_ids, *reused_ids]))
    if paper_ids or skipped_dupes or errors:
        recent = list(dict.fromkeys([*(prefs.get("subscription_paper_ids") or []), *paper_ids]))[-200:]
        patch_profile_preferences(
            session,
            user_id,
            {
                "subscriptions": subscriptions,
                "subscription_paper_ids": recent,
                "last_subscription_sync_at": datetime.now(timezone.utc).isoformat(),
                "last_subscription_sync_stats": {
                    "fetched": len(payloads) + skipped_dupes,
                    "created": created,
                    "updated": updated,
                    "deduped": skipped_dupes,
                    "errors": errors[:5],
                },
            },
        )

    message = f"同步完成：抓取 {len(payloads)} 篇，新建 {created}，更新 {updated}"
    if skipped_dupes:
        message += f"，去重跳过 {skipped_dupes}"
    if errors:
        message += f"；部分失败 {len(errors)} 项"
    return SubscriptionSyncResult(
        user_id=user_id,
        fetched=len(payloads),
        created=created,
        updated=updated,
        deduped=skipped_dupes,
        paper_ids=paper_ids,
        message=message,
        synced_at=datetime.now(timezone.utc),
        errors=errors[:8],
    )


def sync_all_users(session: Session, *, max_per_subscription: int = 3) -> dict:
    from app.model import UserProfile

    profiles = session.query(UserProfile).all()
    total_fetched = total_created = 0
    users = 0
    for profile in profiles:
        subs = normalize_subscriptions((profile.preferences or {}).get("subscriptions"))
        if not any(item.get("enabled", True) for item in subs):
            continue
        users += 1
        result = sync_subscriptions(session, profile.user_id, max_per_subscription=max_per_subscription)
        total_fetched += result.fetched
        total_created += result.created
    return {"users": users, "fetched": total_fetched, "created": total_created}


__all__ = [
    "normalize_subscriptions",
    "list_subscriptions",
    "save_subscriptions",
    "sync_subscriptions",
    "sync_all_users",
]
