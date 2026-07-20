"""Personalized recommendations: topics, reading history, and subscription feed."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import Paper, UserAction
from app.repository.papers import list_papers
from app.schema.papers import PaperItem
from app.service.papers import to_item
from app.service.profile import get_profile
from app.service.subscriptions import normalize_subscriptions


def daily_picks(session: Session, limit: int = 3) -> list[PaperItem]:
    papers, _ = list_papers(
        session,
        keyword=None,
        keywords=None,
        author=None,
        category=None,
        published_from=None,
        published_to=None,
        page=1,
        page_size=min(max(limit * 3, limit), 50),
    )
    items = []
    for paper in papers[:limit]:
        item = to_item(paper)
        item.reason = "每日精选 · 库内最新论文"
        item.recommend_source = "daily"
        items.append(item)
    return items


def _annotate(item: PaperItem, *, reason: str, source: str) -> PaperItem:
    item.reason = reason
    item.recommend_source = source
    return item


def _history_topics(session: Session, user_id: str) -> list[str]:
    paper_ids = session.scalars(
        select(UserAction.paper_id)
        .where(
            UserAction.user_id == user_id,
            UserAction.action_type.in_(("favorite", "reading_history")),
        )
        .order_by(UserAction.occurred_at.desc())
        .limit(20)
    ).all()
    if not paper_ids:
        return []
    papers = session.scalars(select(Paper).where(Paper.id.in_(list(dict.fromkeys(paper_ids))))).all()
    topics: list[str] = []
    for paper in papers:
        cat = (paper.primary_category or "").strip()
        if cat and cat not in topics:
            topics.append(cat)
    return topics[:8]


def profile_recommendations(
    session: Session,
    *,
    user_id: str,
    persona: str | None = None,
    topics: list[str] | None = None,
    limit: int = 3,
    exclude_ids: list[int] | None = None,
) -> list[PaperItem]:
    profile = get_profile(session, user_id)
    wanted_topics = list(topics or profile.topics or [])
    history_topics = _history_topics(session, user_id)
    for topic in history_topics:
        if topic not in wanted_topics:
            wanted_topics.append(topic)

    excluded = set(exclude_ids or [])
    excluded.update(
        session.scalars(
            select(UserAction.paper_id).where(
                UserAction.user_id == user_id,
                UserAction.action_type == "favorite",
            )
        ).all()
    )

    persona_label = persona or profile.persona or "研究"
    papers, _ = list_papers(
        session,
        keyword=None,
        keywords=wanted_topics or None,
        author=None,
        category=None,
        published_from=None,
        published_to=None,
        page=1,
        page_size=50,
    )
    if not papers:
        papers, _ = list_papers(
            session,
            keyword=None,
            keywords=None,
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=1,
            page_size=50,
        )

    items: list[PaperItem] = []
    for paper in papers:
        if paper.id in excluded:
            continue
        matched = [
            topic
            for topic in wanted_topics
            if topic
            and (
                topic.casefold() in (paper.title or "").casefold()
                or topic.casefold() in (paper.abstract or "").casefold()
                or topic.casefold() in (paper.primary_category or "").casefold()
            )
        ]
        if matched:
            reason = f"匹配兴趣：{', '.join(matched[:3])} · {persona_label}模式"
        elif wanted_topics:
            reason = f"按画像方向补充 · {persona_label}模式"
        else:
            reason = f"热门补充 · {persona_label}模式"
        items.append(_annotate(to_item(paper), reason=reason, source="profile"))
        if len(items) >= limit:
            break
    return items


def subscription_recommendations(
    session: Session,
    *,
    user_id: str,
    limit: int = 6,
    exclude_ids: list[int] | None = None,
) -> list[PaperItem]:
    profile = get_profile(session, user_id)
    prefs = dict(profile.preferences or {})
    subscriptions = normalize_subscriptions(prefs.get("subscriptions"))
    enabled = [item for item in subscriptions if item.get("enabled", True)]
    excluded = set(exclude_ids or [])

    recent_ids = [int(x) for x in (prefs.get("subscription_paper_ids") or []) if str(x).isdigit()]
    recent_ids = [pid for pid in recent_ids if pid not in excluded][-50:]

    items: list[PaperItem] = []
    if recent_ids:
        papers = session.scalars(
            select(Paper)
            .where(Paper.id.in_(recent_ids), Paper.deleted_at.is_(None))
            .order_by(Paper.published_at.desc().nullslast(), Paper.id.desc())
        ).all()
        by_id = {paper.id: paper for paper in papers}
        for pid in reversed(recent_ids):
            paper = by_id.get(pid)
            if not paper:
                continue
            label = paper.primary_category or "订阅"
            items.append(
                _annotate(
                    to_item(paper),
                    reason=f"来自订阅同步 · {label}",
                    source="subscription",
                )
            )
            if len(items) >= limit:
                return items

    # Fallback: match enabled subscription values against library
    keywords = [item["value"] for item in enabled]
    if not keywords:
        return items
    papers, _ = list_papers(
        session,
        keyword=None,
        keywords=keywords,
        author=None,
        category=None,
        published_from=None,
        published_to=None,
        page=1,
        page_size=40,
    )
    seen = {item.paper_id for item in items}
    for paper in papers:
        if paper.id in excluded or paper.id in seen:
            continue
        matched = next(
            (
                item["value"]
                for item in enabled
                if item["value"].casefold() in " ".join(
                    [paper.title or "", paper.abstract or "", paper.primary_category or ""]
                ).casefold()
            ),
            keywords[0],
        )
        items.append(
            _annotate(
                to_item(paper),
                reason=f"匹配订阅「{matched}」",
                source="subscription",
            )
        )
        if len(items) >= limit:
            break
    return items


__all__ = [
    "daily_picks",
    "profile_recommendations",
    "subscription_recommendations",
]
