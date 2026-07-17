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
    action = UserAction(
        user_id=payload.user_id,
        paper_id=payload.paper_id,
        action_type=payload.action_type,
        payload_json=payload.payload_json,
    )
    session.add(action)
    session.commit()
    session.refresh(action)
    return to_action(action), True


def list_actions(session: Session, user_id: str, paper_id: int | None, action_type: str | None) -> list[UserActionItem]:
    stmt = select(UserAction).where(UserAction.user_id == user_id)
    if paper_id is not None:
        stmt = stmt.where(UserAction.paper_id == paper_id)
    if action_type is not None:
        if action_type not in ACTION_TYPES:
            raise ValueError("VALIDATION_ERROR")
        stmt = stmt.where(UserAction.action_type == action_type)
    actions = session.scalars(stmt.order_by(UserAction.occurred_at.desc(), UserAction.id.desc())).all()
    return [to_action(action) for action in actions]


def update_action(session: Session, action_id: int, payload: UserActionUpdate) -> UserActionItem:
    action = session.get(UserAction, action_id)
    if action is None:
        raise ValueError("ACTION_NOT_FOUND")
    action.payload_json = payload.payload_json
    session.commit()
    session.refresh(action)
    return to_action(action)


def delete_action(session: Session, action_id: int) -> None:
    action = session.get(UserAction, action_id)
    if action is None:
        raise ValueError("ACTION_NOT_FOUND")
    session.delete(action)
    session.commit()
