"""HTTP helpers for PaperMate system tests."""
from __future__ import annotations

import os
import uuid
from typing import Any

import httpx


def base_url() -> str:
    return os.environ.get("PAPERMATE_BASE_URL", "http://10.119.9.119").rstrip("/")


def api_prefix() -> str:
    prefix = os.environ.get("PAPERMATE_API_PREFIX", "/api")
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    return prefix.rstrip("/")


class ApiClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns = client is None
        self.client = client or httpx.Client(base_url=base_url(), timeout=60.0)
        self.token: str | None = None

    def close(self) -> None:
        if self._owns:
            self.client.close()

    def url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{api_prefix()}{path}"

    def headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(self.headers())
        headers.update(kwargs.pop("headers", {}) or {})
        return self.client.request(method, self.url(path), headers=headers, **kwargs)

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)

    def json_ok(self, response: httpx.Response) -> dict[str, Any]:
        response.raise_for_status()
        body = response.json()
        assert body.get("code") == "OK", body
        return body

    def register(self, email: str, password: str) -> dict[str, Any]:
        response = self.post("/auth/register", json={"email": email, "password": password})
        body = self.json_ok(response)
        data = body["data"]
        self.token = data["access_token"]
        return data

    def login(self, email: str, password: str) -> httpx.Response:
        response = self.post("/auth/login", json={"email": email, "password": password})
        if response.status_code == 200 and response.json().get("code") == "OK":
            self.token = response.json()["data"]["access_token"]
        return response

    def unique_email(self, prefix: str = "st") -> str:
        return f"{prefix}.{uuid.uuid4().hex[:10]}@systemtest.local"
