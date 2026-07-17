from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import PaperUpsert, UserActionInput, UserActionUpdate
from app.service.learning import create_action, delete_action, list_actions, update_action
from app.service.papers import batch_upsert_papers
from sqlalchemy.orm import Session


def make_session() -> Session:
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return Session(engine)


def test_learning_crud_and_favorite_idempotency() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="learning-paper", title="Learning Paper")]).items[0].paper_id
        payload = UserActionInput(user_id="user-1", paper_id=paper_id, action_type="favorite", payload_json={"favorite": True})
        first, _ = create_action(session, payload)
        second, _ = create_action(session, payload)
        assert second.id == first.id
        updated = update_action(session, first.id, UserActionUpdate(payload_json={"favorite": False}))
        assert updated.payload_json["favorite"] is False
        assert len(list_actions(session, "user-1", None, "favorite")) == 1
        delete_action(session, first.id)
        assert list_actions(session, "user-1", None, None) == []


def test_learning_validation_and_not_found() -> None:
    with make_session() as session:
        try:
            create_action(session, UserActionInput(user_id="u", paper_id=999, action_type="favorite"))
        except ValueError as exc:
            assert str(exc) == "PAPER_NOT_FOUND"
        else:
            raise AssertionError("expected PAPER_NOT_FOUND")
        try:
            delete_action(session, 999)
        except ValueError as exc:
            assert str(exc) == "ACTION_NOT_FOUND"
        else:
            raise AssertionError("expected ACTION_NOT_FOUND")
