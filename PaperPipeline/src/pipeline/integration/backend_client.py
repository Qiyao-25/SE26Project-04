"""Small HTTP adapter for persisting pipeline output in member C backend."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .contracts import make_idempotency_key, unwrap_api_response


class BackendClient:
    def __init__(self, api_base: str, timeout_s: float = 10.0, worker_token: str | None = None):
        self.api_base = api_base.rstrip("/")
        self.timeout_s = timeout_s
        self.worker_token = worker_token or os.environ.get("PAPERMATE_WORKER_TOKEN", "")

    def _request(self, path: str, method: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        request_headers = {
            "Content-Type": "application/json",
            "User-Agent": "PaperMate-Pipeline/0.4",
            **(headers or {}),
        }
        if self.worker_token:
            request_headers["X-Worker-Token"] = self.worker_token
        request = urllib.request.Request(
            f"{self.api_base}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                payload = unwrap_api_response(json.loads(response.read().decode()))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"HTTP request failed {path}: {exc}") from exc
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

    def claim_task(self, worker_id: str) -> dict | None:
        return self._request("/api/tasks/claim", "POST", {"worker_id": worker_id})

    def get_task(self, task_id: int) -> dict:
        return self._request(f"/api/tasks/{task_id}", "GET")

    def get_paper(self, paper_id: int) -> dict:
        return self._request(f"/api/papers/{paper_id}", "GET")

    def update_task(self, task_id: int, status: str, error_code: str | None = None, stage: str | None = None) -> dict:
        body: dict[str, Any] = {"status": status}
        if error_code:
            body["error_code"] = error_code[:64]
        if stage:
            body["stage"] = stage[:32]
        return self._request(f"/api/tasks/{task_id}", "PATCH", body)

    def retry_task(self, task_id: int) -> dict:
        return self._request(f"/api/tasks/{task_id}/retry", "POST")

    def recover_stale_tasks(self, timeout_seconds: int = 900) -> dict:
        query = urllib.parse.urlencode({"timeout_seconds": timeout_seconds})
        return self._request(f"/api/tasks/recover-stale?{query}", "POST")

    def get_queue_stats(self, timeout_seconds: int = 900) -> dict:
        query = urllib.parse.urlencode({"timeout_seconds": timeout_seconds})
        return self._request(f"/api/tasks/stats?{query}", "GET")

    def save_structured_results(self, task_id: int, results: list[dict[str, Any]]) -> dict:
        return self._request(f"/api/tasks/{task_id}/results", "POST", {"results": results})

    def save_chunks(self, paper_id: int, chunks: list[dict[str, Any]]) -> dict:
        return self._request(f"/api/papers/{paper_id}/chunks", "POST", {"chunks": chunks})

    def finalize_parse_result(self, task_id: int, chunks: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict:
        return self._request(
            f"/api/tasks/{task_id}/finalize",
            "POST",
            {"chunks": chunks, "results": results},
        )


__all__ = ["BackendClient"]
