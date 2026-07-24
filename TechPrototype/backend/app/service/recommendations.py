"""Personalized recommendations: topics, reading history, and subscription feed."""

from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import Paper, StructuredResult, UserAction
from app.repository.papers import list_papers
from app.schema.papers import PaperItem
from app.service.papers import to_item
from app.service.profile import get_profile
from app.service.subscriptions import normalize_subscriptions


def daily_picks(
    session: Session,
    limit: int = 3,
    *,
    exclude_ids: list[int] | None = None,
) -> list[PaperItem]:
    """Random sample from a recent paper pool so refresh yields new picks."""
    excluded = set(exclude_ids or [])
    pool_size = min(max(limit * 12, 30), 80)
    papers, _ = list_papers(
        session,
        keyword=None,
        keywords=None,
        author=None,
        category=None,
        published_from=None,
        published_to=None,
        page=1,
        page_size=pool_size,
    )
    candidates = [paper for paper in papers if paper.id not in excluded]
    if not candidates:
        candidates = papers
    if not candidates:
        return []
    picked = random.sample(candidates, k=min(limit, len(candidates)))
    items: list[PaperItem] = []
    for paper in picked:
        item = to_item(paper)
        item.reason = "每日精选 · 库内随机论文"
        item.recommend_source = "daily"
        items.append(item)
    return items


def _annotate(item: PaperItem, *, reason: str, source: str) -> PaperItem:
    item.reason = reason
    item.recommend_source = source
    return item


def _recency_boost(paper: Paper) -> float:
    if not paper.published_at:
        return 0.0
    published = paper.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    days = max(0, (datetime.now(timezone.utc) - published).days)
    return max(0.0, 1.0 - days / 365.0)


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


def _concept_names(session: Session, paper_id: int) -> list[str]:
    result = session.scalar(
        select(StructuredResult)
        .where(StructuredResult.paper_id == paper_id, StructuredResult.result_type == "concepts")
        .order_by(StructuredResult.version.desc())
    )
    if not result:
        return []
    names = []
    for item in (result.content_json or {}).get("items", []) or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                names.append(name)
    return names[:8]


def _score_paper(
    paper: Paper,
    wanted_topics: list[str],
    concept_names: list[str] | None = None,
    *,
    prefer_code: bool | None = None,
    author_hints: list[str] | None = None,
) -> tuple[float, list[str]]:
    blob = " ".join([paper.title or "", paper.abstract or "", paper.primary_category or ""]).casefold()
    matched: list[str] = []
    score = 0.0
    for topic in wanted_topics:
        key = topic.casefold()
        if not key:
            continue
        if key in blob:
            matched.append(topic)
            score += 3.0 if key in (paper.title or "").casefold() else 2.0
            if key == (paper.primary_category or "").casefold():
                score += 1.5
    for name in concept_names or []:
        if any(topic.casefold() in name.casefold() or name.casefold() in topic.casefold() for topic in wanted_topics):
            matched.append(name)
            score += 1.2
    score += _recency_boost(paper)
    if paper.ingest_status == "qa_ready":
        score += 0.5

    code_signals = ("github.com", "gitlab.com", "code available", "source code", "open-source", "opensource", "implementation available")
    has_code_signal = any(signal in blob for signal in code_signals)
    if prefer_code is True and has_code_signal:
        matched.append("有代码")
        score += 1.8
    elif prefer_code is False and has_code_signal:
        score -= 0.8

    author_names = []
    for link in paper.authors or []:
        author = getattr(link, "author", None)
        if author is None:
            continue
        for value in (getattr(author, "display_name", None), getattr(author, "normalized_name", None)):
            if value:
                author_names.append(str(value).casefold())
    for hint in author_hints or []:
        key = hint.casefold().strip()
        if not key:
            continue
        if any(key in name or name in key for name in author_names) or key in blob:
            matched.append(hint)
            score += 2.5

    return score, list(dict.fromkeys(matched))


def _preference_boosts(prefs: dict) -> tuple[bool | None, list[str]]:
    prefer_code = prefs.get("code")
    if prefer_code is not None:
        prefer_code = bool(prefer_code)
    raw_authors = str(prefs.get("authors") or "")
    author_hints = [part.strip() for part in raw_authors.replace("；", ",").replace(";", ",").split(",") if part.strip()]
    return prefer_code, author_hints


def _weighted_sample_preserve_order(
    ranked: list[tuple[float, PaperItem]],
    limit: int,
) -> list[PaperItem]:
    """Sample with preference for higher scores, then return in recommendation order."""
    if limit <= 0:
        return []
    if len(ranked) <= limit:
        return [item for _, item in ranked]
    pool = ranked[: max(limit * 10, 24)]
    remaining = list(pool)
    chosen: list[tuple[float, PaperItem]] = []
    while remaining and len(chosen) < limit:
        # Rank bias: earlier (higher score) items are more likely.
        weights = [
            max(score, 0.05) * (1.0 / (index + 1)) * 4.0 + 0.2
            for index, (score, _) in enumerate(remaining)
        ]
        pick_index = random.choices(range(len(remaining)), weights=weights, k=1)[0]
        chosen.append(remaining.pop(pick_index))
    chosen.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in chosen]


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

    prefs = dict(profile.preferences or {})
    prefer_code, author_hints = _preference_boosts(prefs)

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

    ranked: list[tuple[float, PaperItem]] = []
    for paper in papers:
        if paper.id in excluded:
            continue
        concepts = _concept_names(session, paper.id) if wanted_topics else []
        score, matched = _score_paper(
            paper,
            wanted_topics,
            concepts,
            prefer_code=prefer_code,
            author_hints=author_hints,
        )
        if matched:
            reason = f"匹配兴趣：{', '.join(matched[:3])} · {persona_label}模式"
        elif wanted_topics:
            reason = f"按画像方向补充 · {persona_label}模式"
        else:
            reason = f"热门补充 · {persona_label}模式"
        ranked.append((score, _annotate(to_item(paper), reason=reason, source="profile")))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return _weighted_sample_preserve_order(ranked, limit)


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
        scored = []
        for pid in reversed(recent_ids):
            paper = by_id.get(pid)
            if not paper:
                continue
            keywords = [item["value"] for item in enabled]
            score, matched = _score_paper(paper, keywords)
            label = matched[0] if matched else (paper.primary_category or "订阅")
            scored.append(
                (
                    score + _recency_boost(paper),
                    _annotate(to_item(paper), reason=f"来自订阅同步 · {label}", source="subscription"),
                )
            )
        scored.sort(key=lambda row: row[0], reverse=True)
        items = _weighted_sample_preserve_order(scored, limit)
        if len(items) >= limit:
            return items

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
    ranked = []
    for paper in papers:
        if paper.id in excluded or paper.id in seen:
            continue
        score, matched = _score_paper(paper, keywords)
        label = matched[0] if matched else keywords[0]
        ranked.append(
            (score, _annotate(to_item(paper), reason=f"匹配订阅「{label}」", source="subscription"))
        )
    ranked.sort(key=lambda row: row[0], reverse=True)
    for item in _weighted_sample_preserve_order(ranked, max(0, limit - len(items))):
        items.append(item)
        if len(items) >= limit:
            break
    return items


__all__ = [
    "daily_picks",
    "profile_recommendations",
    "subscription_recommendations",
]
