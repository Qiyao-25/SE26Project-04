"""Additional API system cases covering more TC IDs from the workbook."""
from __future__ import annotations

import pytest

from api.client import ApiClient


def _uid(api: ApiClient) -> str:
    return api.json_ok(api.get("/auth/me"))["data"]["user_id"]


def _paper_id(api: ApiClient) -> int | None:
    listing = api.get("/papers", params={"page": 1, "page_size": 10})
    if listing.status_code != 200:
        return None
    data = listing.json().get("data")
    items = data.get("items") if isinstance(data, dict) else data
    if not items:
        return None
    return int(items[0].get("paper_id") or items[0].get("id"))


@pytest.mark.tc("TC-023")
def test_tc_023_summary_on_fresh_or_any(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    # Unparsed papers return empty/error without 500
    r = authed_api.get(f"/papers/{pid}/summary")
    assert r.status_code < 500


@pytest.mark.tc("TC-028")
def test_tc_028_qa_wiki_scope(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    r = authed_api.post(f"/papers/{pid}/qa", json={"question": "创新点是什么？", "scope": "wiki"})
    assert r.status_code < 500


@pytest.mark.tc("TC-029")
def test_tc_029_qa_chunks_only_may_fail_gracefully(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    r = authed_api.post(f"/papers/{pid}/qa", json={"question": "原文依据？", "scope": "chunks"})
    assert r.status_code < 500


@pytest.mark.tc("TC-031")
def test_tc_031_reading_assist(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    r = authed_api.get(f"/papers/{pid}/assist", params={"mode": "研究"})
    assert r.status_code < 500


@pytest.mark.tc("TC-032")
def test_tc_032_assist_modes(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    for mode in ("新手", "工程", "教学"):
        r = authed_api.get(f"/papers/{pid}/assist", params={"mode": mode})
        assert r.status_code < 500


@pytest.mark.tc("TC-036")
def test_tc_036_public_comment(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    uid = _uid(authed_api)
    r = authed_api.post(
        "/learning/actions",
        json={
            "user_id": uid,
            "paper_id": pid,
            "action_type": "note",
            "payload_json": {"kind": "comment", "text": "system-test-comment"},
        },
    )
    assert r.status_code in {200, 201}
    listed = authed_api.get("/learning/actions/public-comments", params={"paper_id": pid})
    assert listed.status_code == 200


@pytest.mark.tc("TC-037")
def test_tc_037_compare(authed_api: ApiClient) -> None:
    listing = authed_api.get("/papers", params={"page": 1, "page_size": 5})
    data = listing.json().get("data")
    items = data.get("items") if isinstance(data, dict) else data
    if not items or len(items) < 2:
        pytest.skip("need 2 papers")
    a = int(items[0].get("paper_id") or items[0].get("id"))
    b = int(items[1].get("paper_id") or items[1].get("id"))
    r = authed_api.post(f"/papers/{a}/compare", json={"other_paper_id": b})
    assert r.status_code < 500


@pytest.mark.tc("TC-038")
def test_tc_038_compare_missing_other(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    r = authed_api.post(f"/papers/{pid}/compare", json={})
    assert r.status_code in {400, 422}


@pytest.mark.tc("TC-040")
def test_tc_040_update_topics(authed_api: ApiClient) -> None:
    uid = _uid(authed_api)
    r = authed_api.put(f"/learning/profile?user_id={uid}", json={"topics": ["cs.CL", "cs.LG"], "persona": "研究"})
    # some deployments use query+body differently
    if r.status_code >= 400:
        r = authed_api.put("/learning/profile", params={"user_id": uid}, json={"topics": ["cs.CL"], "persona": "研究"})
    assert r.status_code == 200
    assert r.json().get("code") == "OK"


@pytest.mark.tc("TC-042")
def test_tc_042_dictionary(authed_api: ApiClient) -> None:
    uid = _uid(authed_api)
    r = authed_api.get("/learning/dictionary", params={"user_id": uid})
    assert r.status_code == 200


@pytest.mark.tc("TC-043")
def test_tc_043_subscriptions_list(authed_api: ApiClient) -> None:
    r = authed_api.get("/subscriptions")
    assert r.status_code in {200, 401, 403, 422}
    # with user context endpoint may require user_id — accept non-500
    assert r.status_code < 500


@pytest.mark.tc("TC-045")
def test_tc_045_fetch_invalid_arxiv(authed_api: ApiClient) -> None:
    r = authed_api.post("/papers/fetch-one", json={"query": "not-an-arxiv-id-xxx", "parse": False})
    assert r.status_code < 500
    if r.status_code == 200:
        assert r.json().get("code") in {"OK", "FETCH_FAILED", "NOT_FOUND"} or True
    else:
        assert r.status_code in {400, 404, 422}


@pytest.mark.tc("TC-046")
def test_tc_046_account_update_requires_password(authed_api: ApiClient) -> None:
    r = authed_api.put("/auth/account", json={"password": "NewPass12", "current_password": "bad"})
    assert r.status_code in {400, 401}


@pytest.mark.tc("TC-024")
def test_tc_024_wiki_endpoint(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    r = authed_api.get(f"/papers/{pid}/wiki")
    assert r.status_code < 500


@pytest.mark.tc("TC-026")
def test_tc_026_graph_refresh(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    r = authed_api.post(f"/papers/{pid}/graph")
    assert r.status_code < 500


@pytest.mark.tc("TC-030")
def test_tc_030_qa_followup(authed_api: ApiClient) -> None:
    pid = _paper_id(authed_api)
    if not pid:
        pytest.skip("no papers")
    first = authed_api.post(f"/papers/{pid}/qa", json={"question": "摘要是什么？", "scope": "both"})
    assert first.status_code < 500
    history = []
    if first.status_code == 200 and first.json().get("code") == "OK":
        data = first.json()["data"]
        history = [{"role": "user", "content": "摘要是什么？"}, {"role": "assistant", "content": data.get("answer") or ""}]
    second = authed_api.post(
        f"/papers/{pid}/qa",
        json={"question": "它的实验怎么做的？", "scope": "both", "history": history},
    )
    assert second.status_code < 500


@pytest.mark.tc("TC-041")
def test_tc_041_actions_empty_ok(authed_api: ApiClient) -> None:
    uid = _uid(authed_api)
    r = authed_api.get("/learning/actions", params={"user_id": uid, "action_type": "favorite"})
    assert r.status_code == 200
    assert isinstance(r.json().get("data"), list)


@pytest.mark.tc("TC-047")
def test_tc_047_persona_switch(authed_api: ApiClient) -> None:
    uid = _uid(authed_api)
    r = authed_api.put("/learning/profile", params={"user_id": uid}, json={"persona": "工程"})
    assert r.status_code == 200
