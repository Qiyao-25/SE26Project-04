"""Small HTTP adapter for persisting pipeline output in member C backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .contracts import make_idempotency_key, unwrap_api_response


class BackendClient:
    def __init__(self, api_base: str, timeout_s: float = 10.0):
        self.api_base = api_base.rstrip("/")
        self.timeout_s = timeout_s

    def _request(self, path: str, method: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        request = urllib.request.Request(
            f"{self.api_base}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", **(headers or {})},
            method=method,
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            payload = unwrap_api_response(json.loads(response.read().decode()))
        return payload

    def create_parse_task(self, paper_id: int, arxiv_id: str, task_type: str = "full_parse") -> dict:
        return self._request(
            f"/api/papers/{paper_id}/parse",
            "POST",
            {"task_type": task_type},
            {"Idempotency-Key": make_idempotency_key(arxiv_id)},
        )

    def list_tasks(self, status: str = "queued", limit: int = 20) -> list[dict]:
        query = urllib.parse.urlencode({"status": status, "limit": limit})
        return self._request(f"/api/tasks?{query}", "GET")

    def get_task(self, task_id: int) -> dict:
        return self._request(f"/api/tasks/{task_id}", "GET")

    def get_paper(self, paper_id: int) -> dict:
        return self._request(f"/api/papers/{paper_id}", "GET")

    def update_task(self, task_id: int, status: str, error_code: str | None = None) -> dict:
        body: dict[str, Any] = {"status": status}
        if error_code:
            body["error_code"] = error_code[:64]
        return self._request(f"/api/tasks/{task_id}", "PATCH", body)

    def save_structured_results(self, task_id: int, results: list[dict[str, Any]]) -> dict:
        return self._request(f"/api/tasks/{task_id}/results", "POST", {"results": results})

    def save_chunks(self, paper_id: int, chunks: list[dict[str, Any]]) -> dict:
        return self._request(f"/api/papers/{paper_id}/chunks", "POST", {"chunks": chunks})


__all__ = ["BackendClient"]
