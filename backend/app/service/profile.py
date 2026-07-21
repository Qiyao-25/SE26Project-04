from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import Paper, StructuredResult, UserAction, UserProfile
from app.schema.papers import DictionaryEntry, PERSONAS, UserProfileData, UserProfileUpdate


def _normalize_topics(topics: list[str]) -> list[str]:
    result: list[str] = []
    for topic in topics:
        value = str(topic).strip()
        if value and value not in result:
            result.append(value)
    return result[:20]


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

    if payload.persona is not None:
        profile.persona = payload.persona if payload.persona in PERSONAS else profile.persona
    if payload.topics is not None:
        profile.topics = _normalize_topics(payload.topics)
    if payload.preferences is not None:
        merged = dict(profile.preferences or {})
        merged.update(payload.preferences)
        profile.preferences = merged

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


def get_dictionary(session: Session, user_id: str, limit: int = 40) -> list[DictionaryEntry]:
    profile = _get_or_create(session, user_id)
    hidden = {
        str(term).casefold().strip()
        for term in (dict(profile.preferences or {}).get("hidden_dictionary_terms") or [])
        if str(term).strip()
    }
    action_paper_ids = session.scalars(
        select(UserAction.paper_id)
        .where(UserAction.user_id == user_id, UserAction.action_type.in_(("favorite", "reading_history")))
        .order_by(UserAction.occurred_at.desc())
        .limit(30)
    ).all()
    paper_ids = list(dict.fromkeys(action_paper_ids))
    stmt = select(Paper).where(Paper.deleted_at.is_(None), Paper.ingest_status == "qa_ready")
    if paper_ids:
        stmt = stmt.where(Paper.id.in_(paper_ids))
    papers = session.scalars(stmt.order_by(Paper.updated_at.desc()).limit(30)).all()
    if not papers and paper_ids:
        papers = session.scalars(
            select(Paper).where(Paper.id.in_(paper_ids), Paper.deleted_at.is_(None)).limit(30)
        ).all()

    entries: dict[str, DictionaryEntry] = {}
    for paper in papers:
        concepts = session.scalar(
            select(StructuredResult).where(
                StructuredResult.paper_id == paper.id,
                StructuredResult.result_type == "concepts",
            ).order_by(StructuredResult.version.desc())
        )
        for item in ((concepts.content_json.get("items", []) if concepts else []) or []):
            if not isinstance(item, dict):
                continue
            term = str(item.get("name") or "").strip()
            if not term or term.casefold() in hidden:
                continue
            entry = entries.setdefault(term.casefold(), DictionaryEntry(term=term, description=str(item.get("description") or term)))
            if paper.id not in entry.paper_ids:
                entry.paper_ids.append(paper.id)
                entry.paper_titles.append(paper.title)
            if len(entries) >= limit:
                break
        if len(entries) >= limit:
            break
    return list(entries.values())[:limit]
