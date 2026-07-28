from collections import Counter
from datetime import datetime, timezone
import re

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.model import Paper, StructuredResult, UserAction, UserProfile
from app.schema.papers import DictionaryEntry, PERSONAS, UserProfileData, UserProfileUpdate


# Low-signal labels produced by summarize fallback / legacy wiki adapters.
_NOISE_TERMS = {
    "核心贡献",
    "core concept",
    "core contribution",
    "concept",
    "概念",
    "未命名概念",
}

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#-]{1,}|[\u4e00-\u9fff]{2,}")

# Behavior → interest topics (A/B): auto-fill with locked/excluded preferences.
_BEHAVIOR_ACTIONS = ("favorite", "reading_history", "note", "reading_progress")
_AUTO_TOPIC_LIMIT = 12
_PREF_LOCKED = "locked_topics"
_PREF_EXCLUDED = "excluded_topics"
_PREF_AUTO_ENABLED = "auto_topics_enabled"


def _normalize_topics(topics: list[str] | None) -> list[str]:
    result: list[str] = []
    for topic in topics or []:
        value = str(topic).strip()
        if value and value not in result:
            result.append(value)
    return result[:20]


def _topic_key(value: str) -> str:
    return str(value or "").strip().casefold()


def _pref_topic_list(prefs: dict, key: str) -> list[str]:
    return _normalize_topics(prefs.get(key) if isinstance(prefs, dict) else None)


def derive_topics_from_behavior(session: Session, user_id: str, *, limit: int = _AUTO_TOPIC_LIMIT) -> list[str]:
    """Rank arXiv categories from reading / favorite / note actions (favorites weigh more)."""
    rows = session.execute(
        select(UserAction.paper_id, UserAction.action_type)
        .where(
            UserAction.user_id == user_id,
            UserAction.action_type.in_(_BEHAVIOR_ACTIONS),
        )
        .order_by(UserAction.occurred_at.desc())
        .limit(80)
    ).all()
    paper_ids = [int(pid) for pid, _action in rows if pid is not None]
    if not paper_ids:
        return []

    papers = session.scalars(select(Paper).where(Paper.id.in_(list(dict.fromkeys(paper_ids))))).all()
    by_id = {paper.id: paper for paper in papers}
    affinity: Counter[str] = Counter()
    order: list[str] = []
    for pid, action in rows:
        paper = by_id.get(int(pid))
        if paper is None:
            continue
        cat = (paper.primary_category or "").strip()
        if not cat:
            continue
        weight = 2.0 if action == "favorite" else 1.0
        affinity[cat] += weight
        root = cat.split(".", 1)[0]
        if root and root != cat:
            affinity[root] += weight * 0.35
        if cat not in order:
            order.append(cat)

    ranked = sorted(order, key=lambda topic: (-affinity.get(topic, 0), order.index(topic)))
    return ranked[: max(1, min(limit, 20))]


def merge_auto_topics(
    *,
    locked: list[str],
    auto: list[str],
    excluded: list[str],
    limit: int = 20,
) -> list[str]:
    """B: locked always kept; auto fills remaining slots unless excluded."""
    blocked = {_topic_key(item) for item in excluded}
    merged: list[str] = []
    for topic in _normalize_topics(locked):
        if _topic_key(topic) in blocked:
            continue
        merged.append(topic)
    for topic in _normalize_topics(auto):
        key = _topic_key(topic)
        if key in blocked or key in {_topic_key(item) for item in merged}:
            continue
        merged.append(topic)
        if len(merged) >= limit:
            break
    return merged[:limit]


def sync_topics_from_behavior(session: Session, user_id: str) -> UserProfileData | None:
    """
    Persist profile.topics from behavior (A) respecting locked/excluded (B).

    preferences:
      - auto_topics_enabled: default True; set False to pause auto sync
      - locked_topics: never removed by sync
      - excluded_topics: never added by sync
    """
    user_id = (user_id or "").strip()
    if not user_id:
        return None
    profile = _get_or_create(session, user_id)
    prefs = dict(profile.preferences or {})
    if prefs.get(_PREF_AUTO_ENABLED) is False:
        return _to_data(profile)

    locked = _pref_topic_list(prefs, _PREF_LOCKED)
    excluded = _pref_topic_list(prefs, _PREF_EXCLUDED)
    auto = derive_topics_from_behavior(session, user_id)
    next_topics = merge_auto_topics(locked=locked, auto=auto, excluded=excluded)
    if list(profile.topics or []) == next_topics:
        return _to_data(profile)

    profile.topics = next_topics
    profile.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(profile)
    return _to_data(profile)


def _to_data(profile: UserProfile) -> UserProfileData:
    return UserProfileData(
        user_id=profile.user_id,
        persona=profile.persona,
        topics=list(profile.topics or []),
        preferences=dict(profile.preferences or {}),
    )


def _get_or_create(session: Session, user_id: str) -> UserProfile:
    profile = session.get(UserProfile, user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id, persona="研究", topics=[], preferences={})
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def get_profile(session: Session, user_id: str) -> UserProfileData:
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("USER_ID_INVALID")
    return _to_data(_get_or_create(session, user_id))


def update_profile(session: Session, user_id: str, payload: UserProfileUpdate) -> UserProfileData:
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("USER_ID_INVALID")
    profile = _get_or_create(session, user_id)
    prefs = dict(profile.preferences or {})

    if payload.persona is not None:
        profile.persona = payload.persona if payload.persona in PERSONAS else profile.persona
    if payload.preferences is not None:
        prefs.update(payload.preferences)

    if payload.topics is not None:
        previous = _normalize_topics(profile.topics)
        next_topics = _normalize_topics(payload.topics)
        # B: manual edit locks the chosen set; dropped topics stay excluded from auto-fill.
        locked = _normalize_topics(next_topics)
        excluded = _pref_topic_list(prefs, _PREF_EXCLUDED)
        excluded_keys = {_topic_key(item) for item in excluded}
        for topic in previous:
            if _topic_key(topic) in {_topic_key(item) for item in next_topics}:
                continue
            if _topic_key(topic) not in excluded_keys:
                excluded.append(topic)
                excluded_keys.add(_topic_key(topic))
        # Manual topics are no longer excluded.
        excluded = [item for item in excluded if _topic_key(item) not in {_topic_key(t) for t in next_topics}]
        prefs[_PREF_LOCKED] = locked
        prefs[_PREF_EXCLUDED] = excluded[:40]
        profile.topics = next_topics

    profile.preferences = prefs
    flag_modified(profile, "preferences")
    profile.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(profile)
    return _to_data(profile)


def patch_profile_preferences(session: Session, user_id: str, patch: dict) -> UserProfileData:
    """Merge top-level preference keys without touching persona/topics."""
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("USER_ID_INVALID")
    profile = _get_or_create(session, user_id)
    merged = dict(profile.preferences or {})
    merged.update(patch or {})
    profile.preferences = merged
    profile.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(profile)
    return _to_data(profile)


def _normalize_term(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _is_noise_term(term: str) -> bool:
    key = _normalize_term(term)
    if not key or key in _NOISE_TERMS:
        return True
    if len(key) < 2:
        return True
    if not _TOKEN_RE.search(term or ""):
        return True
    return False


def _concept_fields(item: dict | str) -> tuple[str, str] | None:
    """Normalize concept payloads from concepts rows or kg_graph nodes."""
    if isinstance(item, str):
        term = item.strip()
        if not term:
            return None
        return term, term
    if not isinstance(item, dict):
        return None
    term = str(
        item.get("name")
        or item.get("title")
        or item.get("label")
        or item.get("term")
        or ""
    ).strip()
    if not term:
        return None
    description = str(
        item.get("description")
        or item.get("desc")
        or item.get("definition")
        or term
    ).strip()
    return term[:80], (description or term)[:500]


def _user_paper_ids(session: Session, user_id: str, *, limit: int = 120) -> list[int]:
    """Papers the user actually interacted with (reading / favorite / notes)."""
    action_paper_ids = session.scalars(
        select(UserAction.paper_id)
        .where(
            UserAction.user_id == user_id,
            UserAction.action_type.in_(("favorite", "reading_history", "note")),
        )
        .order_by(UserAction.occurred_at.desc())
        .limit(limit)
    ).all()
    return list(dict.fromkeys(int(pid) for pid in action_paper_ids if pid is not None))


def _latest_structured(session: Session, paper_id: int, result_type: str) -> StructuredResult | None:
    return session.scalar(
        select(StructuredResult)
        .where(
            StructuredResult.paper_id == paper_id,
            StructuredResult.result_type == result_type,
        )
        .order_by(StructuredResult.version.desc())
    )


def _extract_paper_concepts(session: Session, paper: Paper) -> list[tuple[str, str]]:
    """
    Pull concept terms from current parse artifacts:
    1) StructuredResult(result_type=concepts) — primary SummarizeAgent output
    2) legacy wiki_triple
    3) kg_graph concept nodes — secondary
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    concepts_row = _latest_structured(session, paper.id, "concepts")
    raw_items: list = []
    if concepts_row and isinstance(concepts_row.content_json, dict):
        raw_items = list(concepts_row.content_json.get("items") or [])

    if not raw_items:
        wiki_row = _latest_structured(session, paper.id, "wiki_triple")
        if wiki_row and isinstance(wiki_row.content_json, dict):
            legacy = wiki_row.content_json.get("concepts") or wiki_row.content_json.get("concept")
            if isinstance(legacy, list):
                raw_items = legacy
            elif isinstance(legacy, str) and legacy.strip():
                raw_items = [legacy]

    for item in raw_items:
        fields = _concept_fields(item)
        if not fields:
            continue
        term, description = fields
        key = _normalize_term(term)
        if key in seen or _is_noise_term(term):
            continue
        seen.add(key)
        found.append((term, description))

    if found:
        return found

    graph_row = _latest_structured(session, paper.id, "kg_graph")
    nodes = (graph_row.content_json or {}).get("nodes") if graph_row and isinstance(graph_row.content_json, dict) else []
    for node in nodes or []:
        if not isinstance(node, dict) or node.get("type") != "concept":
            continue
        fields = _concept_fields(node)
        if not fields:
            continue
        term, description = fields
        key = _normalize_term(term)
        if key in seen or _is_noise_term(term):
            continue
        if description == term and node.get("description"):
            description = str(node.get("description")).strip()[:500] or term
        seen.add(key)
        found.append((term, description))

    return found


def _paper_has_parse_concepts(session: Session, paper_id: int) -> bool:
    for result_type in ("concepts", "wiki_triple", "kg_graph"):
        row = _latest_structured(session, paper_id, result_type)
        if row is None:
            continue
        payload = row.content_json if isinstance(row.content_json, dict) else {}
        if result_type == "concepts" and payload.get("items"):
            return True
        if result_type == "wiki_triple" and (payload.get("concepts") or payload.get("concept")):
            return True
        if result_type == "kg_graph":
            nodes = payload.get("nodes") or []
            if any(isinstance(node, dict) and node.get("type") == "concept" for node in nodes):
                return True
    return False


def _collect_dictionary_entries(
    session: Session,
    user_id: str,
    *,
    hidden: set[str] | None = None,
    limit: int = 200,
) -> list[DictionaryEntry]:
    """
    Build a personal concept dictionary from the current parse pipeline.

    Scope: papers the user has read / favorited / noted that already have
    structured concepts (SummarizeAgent `concepts` row, legacy wiki, or graph).
    Does not dump unrelated global qa_ready papers.
    """
    blocked = hidden if hidden is not None else set()
    paper_ids = _user_paper_ids(session, user_id)
    if not paper_ids:
        return []

    papers = session.scalars(
        select(Paper).where(
            Paper.id.in_(paper_ids),
            Paper.deleted_at.is_(None),
            Paper.ingest_status.in_(("qa_ready", "parsed")),
        )
    ).all()
    paper_by_id = {paper.id: paper for paper in papers}
    ordered_papers = [paper_by_id[pid] for pid in paper_ids if pid in paper_by_id]

    entries: dict[str, DictionaryEntry] = {}
    occurrence: dict[str, int] = {}

    for paper in ordered_papers:
        if not _paper_has_parse_concepts(session, paper.id):
            continue
        for term, description in _extract_paper_concepts(session, paper):
            key = _normalize_term(term)
            if key in blocked:
                continue
            occurrence[key] = occurrence.get(key, 0) + 1
            entry = entries.get(key)
            if entry is None:
                entries[key] = DictionaryEntry(
                    term=term,
                    description=description,
                    paper_ids=[paper.id],
                    paper_titles=[paper.title or paper.arxiv_id or str(paper.id)],
                )
                continue
            if paper.id not in entry.paper_ids:
                entry.paper_ids.append(paper.id)
                entry.paper_titles.append(paper.title or paper.arxiv_id or str(paper.id))
            if len(description) > len(entry.description or ""):
                entry.description = description

    ranked = sorted(
        entries.items(),
        key=lambda item: (
            occurrence.get(item[0], 0),
            len(item[1].paper_ids),
            len(item[1].description or ""),
        ),
        reverse=True,
    )
    return [entry for _, entry in ranked[:limit]]


def get_dictionary(session: Session, user_id: str, limit: int = 200) -> list[DictionaryEntry]:
    profile = _get_or_create(session, user_id)
    hidden = {
        str(term).casefold().strip()
        for term in (dict(profile.preferences or {}).get("hidden_dictionary_terms") or [])
        if str(term).strip()
    }
    return _collect_dictionary_entries(session, user_id, hidden=hidden, limit=limit)


def clear_dictionary(session: Session, user_id: str) -> dict:
    """Hide every currently available dictionary term for the user (all pages)."""
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("USER_ID_INVALID")
    profile = _get_or_create(session, user_id)
    visible = _collect_dictionary_entries(session, user_id, hidden=set(), limit=500)
    prefs = dict(profile.preferences or {})
    existing = [
        str(term).strip()
        for term in (prefs.get("hidden_dictionary_terms") or [])
        if str(term).strip()
    ]
    seen = {term.casefold() for term in existing}
    merged = list(existing)
    for entry in visible:
        key = entry.term.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry.term)
    prefs["hidden_dictionary_terms"] = merged
    profile.preferences = prefs
    flag_modified(profile, "preferences")
    profile.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(profile)
    return {"cleared": len(visible), "hidden_total": len(merged)}
