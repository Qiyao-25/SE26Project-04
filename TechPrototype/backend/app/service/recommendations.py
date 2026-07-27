"""Personalized paper recommendations: multi-signal ranking with persona weights."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import Paper, StructuredResult, UserAction
from app.repository.papers import list_papers
from app.schema.papers import PaperItem
from app.service.papers import to_item
from app.service.profile import get_dictionary, get_profile
from app.service.subscriptions import normalize_subscriptions

# Persona → feature weight multipliers (base score is then scaled).
PERSONA_WEIGHTS: dict[str, dict[str, float]] = {
    "新手": {
        "topic": 1.1,
        "concept": 1.2,
        "recency": 1.0,
        "qa_ready": 1.6,
        "code": 0.7,
        "author": 0.9,
        "affinity": 1.2,
        "survey": 1.4,
    },
    "研究": {
        "topic": 1.3,
        "concept": 1.4,
        "recency": 1.1,
        "qa_ready": 1.1,
        "code": 0.9,
        "author": 1.2,
        "affinity": 1.3,
        "survey": 1.0,
    },
    "工程": {
        "topic": 1.0,
        "concept": 1.0,
        "recency": 1.2,
        "qa_ready": 1.0,
        "code": 1.8,
        "author": 1.0,
        "affinity": 1.0,
        "survey": 0.7,
    },
    "教学": {
        "topic": 1.2,
        "concept": 1.3,
        "recency": 0.8,
        "qa_ready": 1.5,
        "code": 0.8,
        "author": 1.0,
        "affinity": 1.1,
        "survey": 1.6,
    },
    "管理": {
        "topic": 1.0,
        "concept": 0.9,
        "recency": 1.3,
        "qa_ready": 0.9,
        "code": 0.6,
        "author": 1.1,
        "affinity": 1.0,
        "survey": 1.5,
    },
}

_SURVEY_HINTS = ("survey", "review", "overview", "综述", "回顾", "tutorial", "primer")
_CODE_HINTS = (
    "github.com",
    "gitlab.com",
    "code available",
    "source code",
    "open-source",
    "opensource",
    "implementation available",
    "pytorch",
    "tensorflow",
    "huggingface",
)


def daily_picks(
    session: Session,
    limit: int = 3,
    *,
    exclude_ids: list[int] | None = None,
) -> list[PaperItem]:
    """Quality-biased daily feed: recent + qa_ready + category diversity."""
    excluded = set(exclude_ids or [])
    pool_size = min(max(limit * 40, 80), 200)
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
        sort_by="published_desc",
    )
    candidates = [paper for paper in papers if paper.id not in excluded] or list(papers)
    if not candidates:
        return []

    ranked: list[tuple[float, Paper]] = []
    for paper in candidates:
        score = 1.0 + _recency_boost(paper) * 2.0
        if paper.ingest_status in {"qa_ready", "parsed"}:
            score += 1.5 if paper.ingest_status == "qa_ready" else 0.6
        if paper.abstract:
            score += min(0.8, len(paper.abstract) / 4000.0)
        ranked.append((score, paper))
    ranked.sort(key=lambda row: row[0], reverse=True)

    picked = _diverse_top_k(ranked, limit=limit, category_penalty=1.2)
    items: list[PaperItem] = []
    for score, paper in picked:
        item = to_item(paper)
        bits = ["每日精选"]
        if paper.ingest_status == "qa_ready":
            bits.append("可问答")
        if _recency_boost(paper) >= 0.7:
            bits.append("近期发表")
        if paper.primary_category:
            bits.append(paper.primary_category)
        item.reason = " · ".join(bits)
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


def _persona_weights(persona: str | None) -> dict[str, float]:
    key = (persona or "研究").strip()
    return dict(PERSONA_WEIGHTS.get(key) or PERSONA_WEIGHTS["研究"])


def _unique_keep(values: Iterable[str], *, limit: int = 24) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _history_signals(session: Session, user_id: str, *, limit: int = 40) -> tuple[list[str], Counter[str], set[int]]:
    """Return (topics from history, category affinity counts, interacted paper ids)."""
    rows = session.execute(
        select(UserAction.paper_id, UserAction.action_type)
        .where(
            UserAction.user_id == user_id,
            UserAction.action_type.in_(("favorite", "reading_history", "note", "reading_progress")),
        )
        .order_by(UserAction.occurred_at.desc())
        .limit(limit)
    ).all()
    paper_ids = [int(pid) for pid, _action in rows if pid is not None]
    if not paper_ids:
        return [], Counter(), set()

    papers = session.scalars(select(Paper).where(Paper.id.in_(list(dict.fromkeys(paper_ids))))).all()
    by_id = {paper.id: paper for paper in papers}
    topics: list[str] = []
    affinity: Counter[str] = Counter()
    for pid, action in rows:
        paper = by_id.get(int(pid))
        if paper is None:
            continue
        cat = (paper.primary_category or "").strip()
        weight = 2 if action == "favorite" else 1
        if cat:
            affinity[cat] += weight
            root = cat.split(".", 1)[0]
            if root:
                affinity[root] += weight * 0.5
            if cat not in topics:
                topics.append(cat)
    return topics[:12], affinity, set(paper_ids)


def _dictionary_terms(session: Session, user_id: str) -> list[str]:
    try:
        entries = get_dictionary(session, user_id, limit=40)
    except Exception:  # noqa: BLE001
        return []
    return _unique_keep((getattr(entry, "term", "") for entry in entries), limit=16)


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


def _paper_blob(paper: Paper) -> str:
    return " ".join([paper.title or "", paper.abstract or "", paper.primary_category or ""]).casefold()


def _author_names(paper: Paper) -> list[str]:
    names: list[str] = []
    for link in paper.authors or []:
        author = getattr(link, "author", None)
        if author is None:
            continue
        for value in (getattr(author, "display_name", None), getattr(author, "normalized_name", None)):
            if value:
                names.append(str(value).casefold())
    return names


def _looks_like_survey(paper: Paper) -> bool:
    title = (paper.title or "").casefold()
    return any(hint in title for hint in _SURVEY_HINTS)


def _has_code_signal(blob: str) -> bool:
    return any(signal in blob for signal in _CODE_HINTS)


def _token_overlap(left: str, right: str) -> bool:
    a = left.casefold().strip()
    b = right.casefold().strip()
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    # light token overlap for multi-word concepts
    a_tokens = {tok for tok in re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", a)}
    b_tokens = {tok for tok in re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", b)}
    return bool(a_tokens & b_tokens)


def score_paper(
    paper: Paper,
    wanted_topics: list[str],
    concept_names: list[str] | None = None,
    *,
    prefer_code: bool | None = None,
    author_hints: list[str] | None = None,
    persona: str | None = None,
    category_affinity: Counter[str] | None = None,
    dictionary_terms: list[str] | None = None,
) -> tuple[float, list[str]]:
    """Multi-signal score. Returns (score, matched reason chips)."""
    weights = _persona_weights(persona)
    blob = _paper_blob(paper)
    matched: list[str] = []
    score = 0.0

    for topic in wanted_topics:
        key = topic.casefold().strip()
        if not key:
            continue
        if key in blob or _token_overlap(key, paper.title or "") or _token_overlap(key, paper.primary_category or ""):
            matched.append(topic)
            hit = 3.2 if key in (paper.title or "").casefold() else 2.0
            if key == (paper.primary_category or "").casefold():
                hit += 1.5
            score += hit * weights["topic"]

    for name in concept_names or []:
        if any(_token_overlap(name, topic) for topic in wanted_topics) or any(
            _token_overlap(name, term) for term in (dictionary_terms or [])
        ):
            matched.append(name)
            score += 1.3 * weights["concept"]

    for term in dictionary_terms or []:
        if _token_overlap(term, paper.title or "") or _token_overlap(term, blob):
            if term not in matched:
                matched.append(term)
            score += 1.0 * weights["concept"]

    cat = (paper.primary_category or "").strip()
    if category_affinity and cat:
        boost = float(category_affinity.get(cat, 0)) + 0.5 * float(category_affinity.get(cat.split(".", 1)[0], 0))
        if boost > 0:
            score += min(3.0, math.log1p(boost) * 1.4) * weights["affinity"]
            matched.append(f"相关方向 {cat}")

    score += _recency_boost(paper) * 1.2 * weights["recency"]

    if paper.ingest_status == "qa_ready":
        score += 0.7 * weights["qa_ready"]
        matched.append("可问答")
    elif paper.ingest_status == "parsed":
        score += 0.25 * weights["qa_ready"]

    has_code = _has_code_signal(blob)
    if prefer_code is True and has_code:
        matched.append("有代码")
        score += 2.0 * weights["code"]
    elif prefer_code is True and not has_code:
        score -= 0.3
    elif prefer_code is False and has_code:
        score -= 0.9 * weights["code"]

    if _looks_like_survey(paper):
        matched.append("综述向")
        score += 1.1 * weights["survey"]

    author_names = _author_names(paper)
    for hint in author_hints or []:
        key = hint.casefold().strip()
        if not key:
            continue
        if any(key in name or name in key for name in author_names) or key in blob:
            matched.append(hint)
            score += 2.6 * weights["author"]

    return score, list(dict.fromkeys(matched))


# Back-compat alias used by older tests/imports
_score_paper = score_paper


def _preference_boosts(prefs: dict) -> tuple[bool | None, list[str]]:
    prefer_code = prefs.get("code")
    if prefer_code is not None:
        prefer_code = bool(prefer_code)
    raw_authors = str(prefs.get("authors") or "")
    author_hints = [
        part.strip()
        for part in raw_authors.replace("；", ",").replace(";", ",").split(",")
        if part.strip()
    ]
    return prefer_code, author_hints


def _diverse_top_k(
    ranked: list[tuple[float, Paper | PaperItem]],
    *,
    limit: int,
    category_penalty: float = 0.85,
) -> list[tuple[float, Paper | PaperItem]]:
    """Greedy MMR-style pick: prefer high score, penalize repeated categories."""
    if limit <= 0 or not ranked:
        return []
    remaining = list(ranked)
    chosen: list[tuple[float, Paper | PaperItem]] = []
    cat_counts: Counter[str] = Counter()

    while remaining and len(chosen) < limit:
        best_index = 0
        best_adjusted = float("-inf")
        for index, (score, obj) in enumerate(remaining):
            if isinstance(obj, Paper):
                cat = (obj.primary_category or "").strip() or "unknown"
            else:
                cat = (getattr(obj, "primary_category", None) or "").strip() or "unknown"
            adjusted = score - category_penalty * cat_counts[cat]
            if adjusted > best_adjusted:
                best_adjusted = adjusted
                best_index = index
        score, obj = remaining.pop(best_index)
        chosen.append((score, obj))
        if isinstance(obj, Paper):
            cat = (obj.primary_category or "").strip() or "unknown"
        else:
            cat = (getattr(obj, "primary_category", None) or "").strip() or "unknown"
        cat_counts[cat] += 1
    return chosen


def _recall_candidates(
    session: Session,
    *,
    wanted_topics: list[str],
    author_hints: list[str],
    pool_size: int = 120,
) -> list[Paper]:
    """Multi-channel recall then merge unique papers."""
    by_id: dict[int, Paper] = {}

    def _absorb(papers: list[Paper]) -> None:
        for paper in papers:
            by_id.setdefault(paper.id, paper)

    # Channel 1: topic / keyword hits
    if wanted_topics:
        papers, _ = list_papers(
            session,
            keyword=None,
            keywords=wanted_topics[:12],
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=1,
            page_size=min(pool_size, 100),
            sort_by="published_desc",
        )
        _absorb(papers)

    # Channel 2: author preference
    for hint in author_hints[:3]:
        papers, _ = list_papers(
            session,
            keyword=None,
            keywords=None,
            author=hint,
            category=None,
            published_from=None,
            published_to=None,
            page=1,
            page_size=30,
            sort_by="published_desc",
        )
        _absorb(papers)

    # Channel 3: recent quality pool for cold-start / fill
    if len(by_id) < pool_size // 2:
        papers, _ = list_papers(
            session,
            keyword=None,
            keywords=None,
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=1,
            page_size=min(pool_size, 120),
            sort_by="published_desc",
        )
        _absorb(papers)

    return list(by_id.values())


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
    persona_label = (persona or profile.persona or "研究").strip() or "研究"
    prefs = dict(profile.preferences or {})
    prefer_code, author_hints = _preference_boosts(prefs)

    history_topics, category_affinity, interacted_ids = _history_signals(session, user_id)
    dictionary_terms = _dictionary_terms(session, user_id)

    wanted_topics = _unique_keep(
        list(topics or []) + list(profile.topics or []) + history_topics + dictionary_terms,
        limit=28,
    )

    # Exclude exact favorites / explicit exclude list; history may still inform affinity.
    favorite_ids = set(
        session.scalars(
            select(UserAction.paper_id).where(
                UserAction.user_id == user_id,
                UserAction.action_type == "favorite",
            )
        ).all()
    )
    excluded = set(exclude_ids or []) | favorite_ids

    candidates = _recall_candidates(
        session,
        wanted_topics=wanted_topics,
        author_hints=author_hints,
        pool_size=140,
    )

    ranked: list[tuple[float, PaperItem]] = []
    for paper in candidates:
        if paper.id in excluded:
            continue
        # Soft-penalize already-read papers so refresh surfaces new work,
        # but do not hard-exclude (favorites already excluded).
        concepts = _concept_names(session, paper.id)
        score, matched = score_paper(
            paper,
            wanted_topics,
            concepts,
            prefer_code=prefer_code,
            author_hints=author_hints,
            persona=persona_label,
            category_affinity=category_affinity,
            dictionary_terms=dictionary_terms,
        )
        if paper.id in interacted_ids and paper.id not in favorite_ids:
            score *= 0.72
        if matched:
            reason = f"匹配：{', '.join(matched[:3])} · {persona_label}模式"
        elif wanted_topics:
            reason = f"画像相关补充 · {persona_label}模式"
        else:
            reason = f"热门补充 · {persona_label}模式"
        ranked.append((score, _annotate(to_item(paper), reason=reason, source="profile")))

    ranked.sort(key=lambda row: row[0], reverse=True)
    # Convert to Paper objects for diversity helper via primary_category on PaperItem
    diverse = _diverse_top_k(ranked, limit=limit, category_penalty=0.9)
    return [item for _score, item in diverse]


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
    keywords = [str(item.get("value") or "").strip() for item in enabled if str(item.get("value") or "").strip()]
    prefer_code, author_hints = _preference_boosts(prefs)
    persona_label = profile.persona or "研究"

    recent_ids = [int(x) for x in (prefs.get("subscription_paper_ids") or []) if str(x).isdigit()]
    recent_ids = [pid for pid in dict.fromkeys(reversed(recent_ids)) if pid not in excluded][:80]

    items: list[PaperItem] = []
    if recent_ids:
        papers = session.scalars(
            select(Paper)
            .where(Paper.id.in_(recent_ids), Paper.deleted_at.is_(None))
        ).all()
        by_id = {paper.id: paper for paper in papers}
        scored: list[tuple[float, PaperItem]] = []
        for pid in recent_ids:
            paper = by_id.get(pid)
            if not paper:
                continue
            score, matched = score_paper(
                paper,
                keywords,
                prefer_code=prefer_code,
                author_hints=author_hints,
                persona=persona_label,
            )
            label = matched[0] if matched else (paper.primary_category or "订阅")
            scored.append(
                (
                    score,
                    _annotate(to_item(paper), reason=f"订阅同步 · {label}", source="subscription"),
                )
            )
        scored.sort(key=lambda row: row[0], reverse=True)
        items = [item for _s, item in _diverse_top_k(scored, limit=limit, category_penalty=0.7)]
        if len(items) >= limit:
            return items

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
        page_size=60,
        sort_by="published_desc",
    )
    seen = {item.paper_id for item in items}
    ranked: list[tuple[float, PaperItem]] = []
    for paper in papers:
        if paper.id in excluded or paper.id in seen:
            continue
        score, matched = score_paper(
            paper,
            keywords,
            prefer_code=prefer_code,
            author_hints=author_hints,
            persona=persona_label,
        )
        label = matched[0] if matched else keywords[0]
        ranked.append(
            (score, _annotate(to_item(paper), reason=f"匹配订阅「{label}」", source="subscription"))
        )
    ranked.sort(key=lambda row: row[0], reverse=True)
    for _score, item in _diverse_top_k(ranked, limit=max(0, limit - len(items)), category_penalty=0.7):
        items.append(item)
        if len(items) >= limit:
            break
    return items


__all__ = [
    "PERSONA_WEIGHTS",
    "daily_picks",
    "profile_recommendations",
    "score_paper",
    "subscription_recommendations",
]
