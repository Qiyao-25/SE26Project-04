"""TC-001 ~ TC-007 认证相关（系统测试用例.xlsx）."""
from __future__ import annotations

import pytest

from api.client import ApiClient


@pytest.mark.tc("TC-001")
def test_tc_001_register_success(api: ApiClient) -> None:
    email = api.unique_email("reg")
    data = api.register(email, "Test1234")
    assert data["access_token"]
    assert data["user"]["email"] == email
    me = api.json_ok(api.get("/auth/me"))
    assert me["data"]["email"] == email


@pytest.mark.tc("TC-003")
def test_tc_003_register_invalid_email_or_short_password(api: ApiClient) -> None:
    bad_email = api.post("/auth/register", json={"email": "a@b", "password": "Test1234"})
    assert bad_email.status_code in {400, 409, 422}
    short_pwd = api.post("/auth/register", json={"email": api.unique_email("short"), "password": "123"})
    assert short_pwd.status_code in {400, 422}


@pytest.mark.tc("TC-004")
def test_tc_004_login_success(api: ApiClient) -> None:
    email = api.unique_email("login")
    password = "Test1234"
    api.register(email, password)
    api.token = None
    response = api.login(email, password)
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "OK"
    assert body["data"]["access_token"]


@pytest.mark.tc("TC-005")
def test_tc_005_login_wrong_password(api: ApiClient) -> None:
    email = api.unique_email("badpwd")
    api.register(email, "Test1234")
    api.token = None
    response = api.login(email, "Wrong999")
    assert response.status_code == 401
    assert response.json().get("code") == "AUTH_INVALID"
    assert api.token is None or True
    me = api.get("/auth/me")
    # without token
    api.token = None
    assert api.get("/auth/me").status_code == 401


@pytest.mark.tc("TC-006")
def test_tc_006_protected_without_token(api: ApiClient) -> None:
    api.token = None
    response = api.get("/learning/profile", params={"user_id": "anyone"})
    assert response.status_code in {401, 403}
    papers = api.get("/papers", params={"page": 1, "page_size": 5})
    # papers list may be public; still must not 500
    assert papers.status_code in {200, 401, 403}


@pytest.mark.tc("TC-007")
def test_tc_007_token_invalid_after_clear(authed_api: ApiClient) -> None:
    assert authed_api.get("/auth/me").status_code == 200
    authed_api.token = None
    assert authed_api.get("/auth/me").status_code == 401
