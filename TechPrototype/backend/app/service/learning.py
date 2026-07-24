from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import Paper, UserAction
from app.schema.papers import ACTION_TYPES, UserActionInput, UserActionItem, UserActionUpdate


def to_action(action: UserAction) -> UserActionItem:
    return UserActionItem(
        id=action.id,
        user_id=action.user_id,
        paper_id=action.paper_id,
        action_type=action.action_type,
        payload_json=action.payload_json,
        occurred_at=action.occurred_at,
    )


def validate_action(session: Session, payload: UserActionInput) -> None:
    if payload.action_type not in ACTION_TYPES:
        raise ValueError("VALIDATION_ERROR")
    paper = session.get(Paper, payload.paper_id)
    if paper is None or paper.deleted_at is not None:
        raise ValueError("PAPER_NOT_FOUND")


def create_action(session: Session, payload: UserActionInput) -> tuple[UserActionItem, bool]:
    validate_action(session, payload)
    payload_json = dict(payload.payload_json or {})
    kind = str(payload_json.get("kind") or "note")
    if kind == "comment":
        payload_json["kind"] = "comment"
        payload_json["visibility"] = "public"
    elif kind in {"note", "annotation"}:
        payload_json["kind"] = kind
        payload_json["visibility"] = "private"
    if payload.action_type == "favorite":
        existing = session.scalar(
            select(UserAction).where(
                UserAction.user_id == payload.user_id,
                UserAction.paper_id == payload.paper_id,
                UserAction.action_type == "favorite",
            )
        )
        if existing is not None:
            return to_action(existing), False
    if payload.action_type == "reading_history":
        existing = session.scalar(
            select(UserAction).where(
                UserAction.user_id == payload.user_id,
                UserAction.paper_id == payload.paper_id,
                UserAction.action_type == "reading_history",
            )
        )
        if existing is not None:
            existing.occurred_at = datetime.now(timezone.utc)
            if payload.payload_json is not None:
                existing.payload_json = payload_json
            session.commit()
            session.refresh(existing)
            return to_action(existing), False
    action = UserAction(
        user_id=payload.user_id,
        paper_id=payload.paper_id,
        action_type=payload.action_type,
        payload_json=payload_json,
    )
    session.add(action)
    session.commit()
    session.refresh(action)
    return to_action(action), True


def list_public_comments(session: Session, paper_id: int, *, limit: int = 100) -> list[UserActionItem]:
    paper = session.get(Paper, paper_id)
    if paper is None or paper.deleted_at is not None:
        raise ValueError("PAPER_NOT_FOUND")
    rows = session.scalars(
        select(UserAction)
        .where(UserAction.paper_id == paper_id, UserAction.action_type == "note")
        .order_by(UserAction.occurred_at.desc(), UserAction.id.desc())
        .limit(limit * 3)
    ).all()
    items = []
    for action in rows:
        payload = action.payload_json or {}
        if payload.get("kind") != "comment":
            continue
        items.append(to_action(action))
        if len(items) >= limit:
            break
    return items


def list_actions(session: Session, user_id: str, paper_id: int | None, action_type: str | None) -> list[UserActionItem]:
    stmt = select(UserAction).where(UserAction.user_id == user_id)
    if paper_id is not None:
        stmt = stmt.where(UserAction.paper_id == paper_id)
    if action_type is not None:
        if action_type not in ACTION_TYPES:
            raise ValueError("VALIDATION_ERROR")
        stmt = stmt.where(UserAction.action_type == action_type)
    actions = session.scalars(stmt.order_by(UserAction.occurred_at.desc(), UserAction.id.desc())).all()
    items = [to_action(action) for action in actions]
    # One reading-history row per paper (keep latest).
    if action_type == "reading_history" or action_type is None:
        seen_history: set[int] = set()
        deduped: list[UserActionItem] = []
        for item in items:
            if item.action_type == "reading_history":
                if item.paper_id in seen_history:
                    continue
                seen_history.add(item.paper_id)
            deduped.append(item)
        return deduped
    return items


def update_action(session: Session, action_id: int, payload: UserActionUpdate, user_id: str | None = None) -> UserActionItem:
    action = session.get(UserAction, action_id)
    if action is None:
        raise ValueError("ACTION_NOT_FOUND")
    if user_id is not None and action.user_id != user_id:
        raise ValueError("ACTION_FORBIDDEN")
    action.payload_json = payload.payload_json
    session.commit()
    session.refresh(action)
    return to_action(action)


def delete_action(session: Session, action_id: int, user_id: str | None = None) -> None:
    action = session.get(UserAction, action_id)
    if action is None:
        raise ValueError("ACTION_NOT_FOUND")
    if user_id is not None and action.user_id != user_id:
        raise ValueError("ACTION_FORBIDDEN")
    session.delete(action)
    session.commit()


def delete_actions_by_type(session: Session, user_id: str, action_type: str) -> int:
    if action_type not in ACTION_TYPES:
        raise ValueError("VALIDATION_ERROR")
    rows = session.scalars(
        select(UserAction).where(UserAction.user_id == user_id, UserAction.action_type == action_type)
    ).all()
    for row in rows:
        session.delete(row)
    session.commit()
    return len(rows)
