"""HTTP adapter for member C backend — papers, tasks, chunks, finalize."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .contracts import make_idempotency_key, unwrap_api_response


class BackendClient:
    def __init__(self, api_base: str, timeout_s: float = 30.0):
        self.api_base = api_base.rstrip("/")
        self.timeout_s = timeout_s

    def _request(
        self,
        path: str,
        method: str,
        body: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}{path}",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "PaperMate-Pipeline/0.3", **(headers or {})},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read().decode("utf-8")
                if not raw.strip():
                    return {}
                return unwrap_api_response(json.loads(raw))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc

    def health(self) -> dict:
        return self._request("/health", "GET")

    def batch_upsert_papers(self, papers: list[dict[str, Any]]) -> dict:
        """POST /api/papers/batch — JSON array body."""
        return self._request("/api/papers/batch", "POST", papers)

    def list_papers(self, *, keyword: str = "", page: int = 1, page_size: int = 20) -> dict:
        query = urllib.parse.urlencode(
            {"keyword": keyword, "page": page, "page_size": page_size},
            doseq=True,
        )
        return self._request(f"/api/papers?{query}", "GET")

    def find_paper_id_by_arxiv(self, arxiv_id: str) -> int | None:
        page = self.list_papers(keyword=arxiv_id, page=1, page_size=50)
        items = page.get("items") if isinstance(page, dict) else None
        if not items:
            return None
        for item in items:
            if str(item.get("arxiv_id") or "") == arxiv_id:
                return int(item["paper_id"])
        return int(items[0]["paper_id"]) if items else None

    def create_parse_task(
        self,
        paper_id: int,
        arxiv_id: str,
        task_type: str = "full_parse",
        *,
        force: bool = False,
    ) -> dict:
        return self._request(
            f"/api/papers/{paper_id}/parse",
            "POST",
            {"task_type": task_type, "force": force},
            {"Idempotency-Key": make_idempotency_key(arxiv_id, task_type)},
        )

    def list_tasks(self, status: str = "queued", limit: int = 20) -> list[dict]:
        query = urllib.parse.urlencode({"status": status, "limit": limit})
        data = self._request(f"/api/tasks?{query}", "GET")
        return data if isinstance(data, list) else []

    def get_task(self, task_id: int) -> dict:
        return self._request(f"/api/tasks/{task_id}", "GET")

    def get_paper(self, paper_id: int) -> dict:
        return self._request(f"/api/papers/{paper_id}", "GET")

    def get_wiki(self, paper_id: int) -> dict:
        return self._request(f"/api/papers/{paper_id}/wiki", "GET")

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

    def enqueue_pending(self, limit: int = 20) -> dict:
        query = urllib.parse.urlencode({"limit": limit})
        return self._request(f"/api/tasks/enqueue-pending?{query}", "POST")

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

    def search_chunks(self, *, query: str, arxiv_id: str | None = None, paper_id: int | None = None, top_k: int = 5) -> dict:
        body: dict[str, Any] = {"query": query, "top_k": top_k}
        if arxiv_id:
            body["arxiv_id"] = arxiv_id
        if paper_id is not None:
            body["paper_id"] = paper_id
        return self._request("/api/search/chunks", "POST", body)


__all__ = ["BackendClient"]
