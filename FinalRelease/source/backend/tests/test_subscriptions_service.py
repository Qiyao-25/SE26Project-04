"""Unit tests for subscription service sync paths."""

from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, UserProfile
from app.service.arxiv_client import ArxivPaperMeta
from app.service.subscriptions import (
    list_subscriptions,
    normalize_subscriptions,
    save_subscriptions,
    sync_all_users,
    sync_subscriptions,
)
from tests.test_subscription_collect import FakeClient, _meta


def _session(tmp_path) -> Session:
    engine = create_engine_for(Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'subs-svc.db'}"))
    Base.metadata.create_all(engine)
    return Session(engine)


def test_normalize_list_and_save(tmp_path) -> None:
    with _session(tmp_path) as session:
        saved = save_subscriptions(
            session,
            "u1",
            [
                {"type": "keyword", "value": "Transformer"},
                {"type": "keyword", "value": "transformer"},
                {"type": "category", "value": "cs.CL"},
            ],
        )
        assert len(saved) == 2
        listed = list_subscriptions(session, "u1")
        assert listed[0].value == "Transformer"
        assert normalize_subscriptions(None) == []


def test_sync_with_fake_client(tmp_path) -> None:
    with _session(tmp_path) as session:
        save_subscriptions(
            session,
            "u2",
            [{"type": "category", "value": "cs.LG", "enabled": True}],
        )
        client = FakeClient(
            rss=[_meta("2401.00001"), _meta("2401.00002")],
            pages=[[_meta("2401.00003"), _meta("2401.00004")]],
        )
        result = sync_subscriptions(
            session,
            "u2",
            max_per_subscription=2,
            client=client,
            settings=Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'subs-svc.db'}"),
        )
        assert result.fetched >= 1
        assert result.created >= 1
        assert result.paper_ids


def test_sync_errors_are_recorded(tmp_path) -> None:
    with _session(tmp_path) as session:
        save_subscriptions(session, "u3", [{"type": "keyword", "value": "fail-me", "enabled": True}])

        class BrokenClient:
            def fetch_category_rss(self, *args, **kwargs):
                raise RuntimeError("rss down")

            def search(self, *args, **kwargs):
                raise RuntimeError("api down")

        result = sync_subscriptions(session, "u3", client=BrokenClient())
        assert result.errors
        assert "fail-me" in result.errors[0]


def test_sync_all_users_mocked(tmp_path, monkeypatch) -> None:
    with _session(tmp_path) as session:
        profile = UserProfile(
            user_id="u4",
            persona="研究",
            topics=[],
            preferences={"subscriptions": [{"type": "keyword", "value": "RAG", "enabled": True}]},
        )
        session.add(profile)
        session.commit()

        fake_result = MagicMock(fetched=1, created=1, errors=[], updated=0)
        monkeypatch.setattr("app.service.subscriptions.sync_subscriptions", lambda *args, **kwargs: fake_result)
        summary = sync_all_users(session, max_per_subscription=1)
        assert summary["users"] == 1
        assert summary["fetched"] == 1
        assert summary["created"] == 1


def test_sync_no_enabled_subscriptions(tmp_path) -> None:
    with _session(tmp_path) as session:
        save_subscriptions(session, "u5", [{"type": "keyword", "value": "off", "enabled": False}])
        result = sync_subscriptions(session, "u5")
        assert result.fetched == 0
        assert "没有启用" in result.message
