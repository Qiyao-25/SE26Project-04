"""Tests for in-memory smart-search session store."""

import time

import app.service.search_session_store as store
from app.service.search_session_store import create_search_session, get_search_session


def test_search_session_expires_and_evicts(monkeypatch) -> None:
    now = {"value": 1000.0}
    monkeypatch.setattr(store.time, "time", lambda: now["value"])

    with store._lock:
        store._SESSIONS.clear()

    session = create_search_session(query="attention", plan={"mode": "topic"}, paper_ids=[1, 2], ttl_s=60)
    assert get_search_session(session.session_id) is not None

    now["value"] = 1061.0
    assert get_search_session(session.session_id) is None

    for index in range(store._MAX_SESSIONS + 5):
        create_search_session(query=f"q{index}", plan={}, paper_ids=[index], ttl_s=600)
    with store._lock:
        assert len(store._SESSIONS) <= store._MAX_SESSIONS
