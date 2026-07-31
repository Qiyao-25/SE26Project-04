"""TC-022/025/066/067 等可 API 覆盖的详情、图谱与安全用例."""
from __future__ import annotations

import pytest

from api.client import ApiClient


def _first_paper_id(api: ApiClient) -> int | None:
    listing = api.get("/papers", params={"page": 1, "page_size": 10})
    if listing.status_code != 200:
        return None
    payload = listing.json().get("data")
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not items:
        return None
    return int(items[0].get("paper_id") or items[0].get("id"))


@pytest.mark.tc("TC-022")
def test_tc_022_summary_or_wiki(authed_api: ApiClient) -> None:
    paper_id = _first_paper_id(authed_api)
    if paper_id is None:
        pytest.skip("no papers")
    for path in (f"/papers/{paper_id}/summary", f"/papers/{paper_id}/wiki"):
        response = authed_api.get(path)
        # 未解析时可能 404/空 OK，但不应 500
        assert response.status_code < 500, path


@pytest.mark.tc("TC-025")
def test_tc_025_graph(authed_api: ApiClient) -> None:
    paper_id = _first_paper_id(authed_api)
    if paper_id is None:
        pytest.skip("no papers")
    response = authed_api.get(f"/papers/{paper_id}/graph")
    assert response.status_code < 500


@pytest.mark.tc("TC-027")
def test_tc_027_qa_endpoint_shape(authed_api: ApiClient) -> None:
    paper_id = _first_paper_id(authed_api)
    if paper_id is None:
        pytest.skip("no papers")
    response = authed_api.post(
        f"/papers/{paper_id}/qa",
        json={"question": "这篇论文的核心方法是什么？", "scope": "both"},
    )
    # LLM 未配置时可能 4xx；不应 500 崩溃
    assert response.status_code < 500
    if response.status_code == 200 and response.json().get("code") == "OK":
        data = response.json()["data"]
        assert data.get("answer") or data.get("content") or data.get("message")


@pytest.mark.tc("TC-033")
def test_tc_033_create_note(authed_api: ApiClient) -> None:
    paper_id = _first_paper_id(authed_api)
    if paper_id is None:
        pytest.skip("no papers")
    user_id = authed_api.json_ok(authed_api.get("/auth/me"))["data"]["user_id"]
    response = authed_api.post(
        "/learning/actions",
        json={
            "user_id": user_id,
            "paper_id": paper_id,
            "action_type": "note",
            "payload_json": {"kind": "note", "text": "system-test-note"},
        },
    )
    assert response.status_code in {200, 201}
    if response.status_code in {200, 201}:
        assert response.json().get("code") == "OK"


@pytest.mark.tc("TC-039")
def test_tc_039_learning_profile_and_actions(authed_api: ApiClient) -> None:
    user_id = authed_api.json_ok(authed_api.get("/auth/me"))["data"]["user_id"]
    profile = authed_api.get("/learning/profile", params={"user_id": user_id})
    assert profile.status_code == 200
    assert profile.json().get("code") == "OK"
    actions = authed_api.get("/learning/actions", params={"user_id": user_id})
    assert actions.status_code == 200


@pytest.mark.tc("TC-049")
def test_tc_049_normal_user_admin_forbidden(authed_api: ApiClient) -> None:
    response = authed_api.get("/admin/overview")
    assert response.status_code in {401, 403}


@pytest.mark.tc("TC-066")
def test_tc_066_admin_delete_forbidden_for_user(authed_api: ApiClient) -> None:
    paper_id = _first_paper_id(authed_api) or 1
    response = authed_api.delete(f"/papers/{paper_id}")
    assert response.status_code in {401, 403}
    if response.status_code in {200, 204}:
        pytest.fail("normal user must not soft-delete papers")


@pytest.mark.tc("TC-067")
def test_tc_067_login_injection_safe(api: ApiClient) -> None:
    response = api.login("' OR 1=1--", "' OR 1=1--")
    assert response.status_code in {400, 401, 422}
    assert response.status_code != 500
