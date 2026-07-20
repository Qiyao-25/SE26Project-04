from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import PaperUpsert, UserProfileUpdate
from app.service.papers import batch_upsert_papers
from app.service.profile import get_profile, update_profile
from app.service.recommendations import subscription_recommendations
from app.service.subscriptions import normalize_subscriptions, save_subscriptions


def test_profile_partial_update_preserves_topics(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'partial.db'}")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        update_profile(
            session,
            "u1",
            UserProfileUpdate(persona="工程", topics=["cs.CL", "RAG"], preferences={"code": True}),
        )
        updated = update_profile(session, "u1", UserProfileUpdate(preferences={"subscriptions": [{"key": "1", "type": "keyword", "value": "Transformer", "enabled": True}]}))
        assert updated.persona == "工程"
        assert updated.topics == ["cs.CL", "RAG"]
        assert updated.preferences["code"] is True
        assert updated.preferences["subscriptions"][0]["value"] == "Transformer"


def test_subscription_feed_from_synced_ids(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'subs.db'}")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="2401.00001", title="Transformer Survey", primary_category="cs.CL")],
        ).items[0]
        save_subscriptions(
            session,
            "u2",
            [{"key": "1", "type": "keyword", "value": "Transformer", "enabled": True}],
        )
        update_profile(
            session,
            "u2",
            UserProfileUpdate(
                preferences={
                    "subscription_paper_ids": [paper.paper_id],
                }
            ),
        )
        items = subscription_recommendations(session, user_id="u2", limit=3)
        assert len(items) == 1
        assert items[0].paper_id == paper.paper_id
        assert items[0].recommend_source == "subscription"
        assert "订阅" in (items[0].reason or "")


def test_normalize_subscriptions_dedupes() -> None:
    items = normalize_subscriptions(
        [
            {"type": "keyword", "value": "RAG"},
            {"type": "keyword", "value": "rag"},
            {"type": "category", "value": "cs.CL"},
            {"type": "other", "value": "x"},
        ]
    )
    assert len(items) == 2
    assert items[0]["value"] == "RAG"
    assert items[1]["value"] == "cs.CL"
