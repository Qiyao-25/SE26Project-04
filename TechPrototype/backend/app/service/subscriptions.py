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


def _author_inputs(raw_authors: list[str] | None) -> list[AuthorInput]:
    authors: list[AuthorInput] = []
    for raw in raw_authors or []:
        name = " ".join(str(raw or "").split()).strip()
        if not name:
            continue
        if len(name) > 255:
            name = name[:255].rstrip()
        try:
            authors.append(AuthorInput(name=name))
        except Exception:  # noqa: BLE001
            continue
        if len(authors) >= 20:
            break
    return authors


def _parse_published(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


CODE_SIGNALS = (
    "github.com",
    "gitlab.com",
    "code available",
    "source code",
    "open-source",
    "opensource",
    "implementation available",
    "code release",
)


def _has_code_signal(meta) -> bool:
    blob = f"{meta.title or ''} {meta.abstract or ''}".casefold()
    return any(signal in blob for signal in CODE_SIGNALS)


def _collect_new_metas(
    client: ArxivClient,
    item: dict,
    *,
    want: int,
    existing_ids: set[str],
    batch_seen_ids: set[str],
    page_size: int = 25,
    max_pages: int = 5,
    require_code: bool = False,
) -> tuple[list, int]:
    """Fetch newest-first and keep only papers not already in DB / this sync batch.

    Returns (new_metas, skipped_known_count).
    """
    from app.service.dedupe import normalize_arxiv_id

    if want <= 0:
        return [], 0

    collected: list = []
    skipped = 0
    query = _build_query(item)

    def _accept(meta) -> bool:
        nonlocal skipped
        aid = normalize_arxiv_id(meta.arxiv_id)
        if not aid:
            return False
        if aid in existing_ids or aid in batch_seen_ids:
            skipped += 1
            return False
        if require_code and not _has_code_signal(meta):
            skipped += 1
            return False
        batch_seen_ids.add(aid)
        meta.arxiv_id = aid
        collected.append(meta)
        return True

    # Category: try a wider RSS window first (often works when API is rate-limited).
    if item["type"] == "category":
        try:
            rss_n = min(100, max(page_size, want * 8))
            for meta in client.fetch_category_rss(item["value"], max_results=rss_n):
                _accept(meta)
                if len(collected) >= want:
                    return collected[:want], skipped
            logger.info(
                "subscription_rss_new cat=%s new=%s skipped=%s require_code=%s",
                item["value"],
                len(collected),
                skipped,
                require_code,
            )
        except Exception as rss_exc:  # noqa: BLE001
            logger.warning(
                "subscription_rss_failed cat=%s err=%s; fallback_api",
                item["value"],
                rss_exc,
            )

    # API pagination: walk past already-known papers until we fill `want` new ones.
    for page in range(max_pages):
        if len(collected) >= want:
            break
        start = page * page_size
        try:
            page_metas = client.search(
                search_query=query,
                max_results=page_size,
                start=start,
            )
        except Exception:
            raise
        if not page_metas:
            break
        for meta in page_metas:
            _accept(meta)
            if len(collected) >= want:
                break
        if len(page_metas) < page_size:
            break

    return collected[:want], skipped


def sync_subscriptions(
    session: Session,
    user_id: str,
    *,
    max_per_subscription: int = 5,
    client: ArxivClient | None = None,
    settings=None,
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

    if client is None:
        if settings is not None:
            client = ArxivClient(
                api_base=getattr(settings, "arxiv_api_base", "https://export.arxiv.org/api/query"),
                rss_base=getattr(settings, "arxiv_rss_base", "https://rss.arxiv.org/rss"),
                timeout_s=float(getattr(settings, "arxiv_timeout_s", 60.0)),
                min_interval_s=float(getattr(settings, "arxiv_min_interval_s", 5.0)),
                max_retries=int(getattr(settings, "arxiv_max_retries", 4)),
                rate_limit_wait_s=float(getattr(settings, "arxiv_rate_limit_wait_s", 45.0)),
            )
        else:
            client = ArxivClient()
    payloads: list[PaperUpsert] = []
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    errors: list[str] = []
    skipped_dupes = 0

    from app.service.dedupe import normalize_arxiv_id, normalize_title
    from app.model import Paper
    from sqlalchemy import select

    existing_ids: set[str] = set()
    existing_by_title: dict[str, int] = {}
    for paper in session.scalars(select(Paper).where(Paper.deleted_at.is_(None))).all():
        aid = normalize_arxiv_id(paper.arxiv_id or "")
        if aid:
            existing_ids.add(aid)
        key = normalize_title(paper.title or "")
        if key and key not in existing_by_title:
            existing_by_title[key] = paper.id

    reused_ids: list[int] = []
    page_size = max(10, min(50, max_per_subscription * 5))
    max_pages = 8 if (prefs.get("crawl") or {}).get("codeOnly") else 6
    require_code = bool((prefs.get("crawl") or {}).get("codeOnly"))

    for item in enabled:
        try:
            metas, skipped = _collect_new_metas(
                client,
                item,
                want=max_per_subscription,
                existing_ids=existing_ids,
                batch_seen_ids=seen_ids,
                page_size=page_size,
                max_pages=max_pages,
                require_code=require_code,
            )
            skipped_dupes += skipped
            logger.info(
                "subscription_fetch_new user=%s type=%s value=%s new=%s skipped=%s",
                user_id,
                item["type"],
                item["value"],
                len(metas),
                skipped,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("subscription_fetch_failed user=%s item=%s err=%s", user_id, item, exc)
            errors.append(f"{item['type']}:{item['value']} -> {exc}")
            continue
        for meta in metas:
            title_key = normalize_title(meta.title or "")
            if title_key and title_key in seen_titles:
                skipped_dupes += 1
                continue
            if title_key and title_key in existing_by_title:
                skipped_dupes += 1
                reused_ids.append(existing_by_title[title_key])
                seen_titles.add(title_key)
                continue
            if title_key:
                seen_titles.add(title_key)
            existing_ids.add(normalize_arxiv_id(meta.arxiv_id))
            payloads.append(
                PaperUpsert(
                    arxiv_id=meta.arxiv_id,
                    title=meta.title or meta.arxiv_id,
                    authors=_author_inputs(meta.authors),
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


def sync_all_users(session: Session, *, max_per_subscription: int = 5, settings=None) -> dict:
    from app.model import UserProfile

    profiles = session.query(UserProfile).all()
    total_fetched = total_created = total_errors = 0
    users = 0
    error_samples: list[str] = []
    for profile in profiles:
        subs = normalize_subscriptions((profile.preferences or {}).get("subscriptions"))
        if not any(item.get("enabled", True) for item in subs):
            continue
        users += 1
        result = sync_subscriptions(
            session,
            profile.user_id,
            max_per_subscription=max_per_subscription,
            settings=settings,
        )
        total_fetched += result.fetched
        total_created += result.created
        errs = list(result.errors or [])
        total_errors += len(errs)
        for item in errs:
            if len(error_samples) < 5:
                error_samples.append(item)
    return {
        "users": users,
        "fetched": total_fetched,
        "created": total_created,
        "errors": total_errors,
        "error_samples": error_samples,
    }


__all__ = [
    "normalize_subscriptions",
    "list_subscriptions",
    "save_subscriptions",
    "sync_subscriptions",
    "sync_all_users",
]
