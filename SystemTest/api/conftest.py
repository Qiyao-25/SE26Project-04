from __future__ import annotations

import pytest

from api.client import ApiClient, base_url


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "tc(id): maps to SystemTest case ID e.g. TC-001")


@pytest.fixture(scope="session")
def api_base() -> str:
    return base_url()


@pytest.fixture
def api() -> ApiClient:
    client = ApiClient()
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def authed_api(api: ApiClient) -> ApiClient:
    email = api.unique_email("user")
    password = "Test1234"
    api.register(email, password)
    api._email = email  # type: ignore[attr-defined]
    api._password = password  # type: ignore[attr-defined]
    return api
