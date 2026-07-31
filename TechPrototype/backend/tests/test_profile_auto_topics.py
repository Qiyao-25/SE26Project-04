"""Auto interest topics from reading/favorites with lock/exclude (profile A/B)."""

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import PaperUpsert, UserActionInput, UserProfileUpdate
from app.service.learning import create_action
from app.service.papers import batch_upsert_papers
from app.service.profile import (
    derive_topics_from_behavior,
    get_profile,
    merge_auto_topics,
    sync_topics_from_behavior,
    update_profile,
)


def _session(tmp_path, name: str) -> Session:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / name}")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_merge_auto_topics_respects_lock_and_exclude() -> None:
    assert merge_auto_topics(
        locked=["cs.CL", "RAG"],
        auto=["cs.LG", "cs.CL", "physics.optics"],
        excluded=["physics.optics", "cs.LG"],
    ) == ["cs.CL", "RAG"]
    assert merge_auto_topics(
        locked=["MyTopic"],
        auto=["cs.CL", "cs.LG"],
        excluded=[],
    ) == ["MyTopic", "cs.CL", "cs.LG"]


def test_favorite_and_reading_auto_fill_topics(tmp_path) -> None:
    with _session(tmp_path, "auto_topics.db") as session:
        items = batch_upsert_papers(
            session,
            [
                PaperUpsert(arxiv_id="a-cl", title="CL", primary_category="cs.CL"),
                PaperUpsert(arxiv_id="a-lg", title="LG", primary_category="cs.LG"),
            ],
        ).items
        cl_id, lg_id = [item.paper_id for item in items]

        create_action(
            session,
            UserActionInput(user_id="u1", paper_id=cl_id, action_type="favorite", payload_json={"favorite": True}),
        )
        create_action(
            session,
            UserActionInput(user_id="u1", paper_id=lg_id, action_type="reading_history", payload_json={}),
        )

        profile = get_profile(session, "u1")
        assert "cs.CL" in profile.topics
        assert "cs.LG" in profile.topics
        # Favorites rank ahead of plain reading when both present.
        assert profile.topics.index("cs.CL") < profile.topics.index("cs.LG")
        assert derive_topics_from_behavior(session, "u1")[0] == "cs.CL"


def test_manual_topics_lock_and_exclude_auto_refill(tmp_path) -> None:
    with _session(tmp_path, "lock_topics.db") as session:
        items = batch_upsert_papers(
            session,
            [
                PaperUpsert(arxiv_id="b-cl", title="CL", primary_category="cs.CL"),
                PaperUpsert(arxiv_id="b-lg", title="LG", primary_category="cs.LG"),
                PaperUpsert(arxiv_id="b-cv", title="CV", primary_category="cs.CV"),
            ],
        ).items
        cl_id, lg_id, cv_id = [item.paper_id for item in items]

        create_action(
            session,
            UserActionInput(user_id="u2", paper_id=cl_id, action_type="reading_history", payload_json={}),
        )
        assert "cs.CL" in get_profile(session, "u2").topics

        # User drops cs.CL and keeps a custom locked topic.
        updated = update_profile(
            session,
            "u2",
            UserProfileUpdate(topics=["MyFocus"]),
        )
        assert updated.topics == ["MyFocus"]
        assert updated.preferences.get("locked_topics") == ["MyFocus"]
        assert "cs.CL" in (updated.preferences.get("excluded_topics") or [])

        create_action(
            session,
            UserActionInput(user_id="u2", paper_id=lg_id, action_type="favorite", payload_json={"favorite": True}),
        )
        create_action(
            session,
            UserActionInput(user_id="u2", paper_id=cv_id, action_type="reading_history", payload_json={}),
        )
        create_action(
            session,
            UserActionInput(user_id="u2", paper_id=cl_id, action_type="favorite", payload_json={"favorite": True}),
        )

        profile = get_profile(session, "u2")
        assert profile.topics[0] == "MyFocus"
        assert "cs.LG" in profile.topics
        assert "cs.CV" in profile.topics
        assert "cs.CL" not in profile.topics  # excluded after manual removal


def test_auto_topics_can_be_disabled(tmp_path) -> None:
    with _session(tmp_path, "disable_auto.db") as session:
        item = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="c-cl", title="CL", primary_category="cs.CL")],
        ).items[0]
        update_profile(
            session,
            "u3",
            UserProfileUpdate(topics=[], preferences={"auto_topics_enabled": False}),
        )
        create_action(
            session,
            UserActionInput(user_id="u3", paper_id=item.paper_id, action_type="favorite", payload_json={"favorite": True}),
        )
        assert get_profile(session, "u3").topics == []
        # Explicit sync still no-ops when disabled.
        sync_topics_from_behavior(session, "u3")
        assert get_profile(session, "u3").topics == []
