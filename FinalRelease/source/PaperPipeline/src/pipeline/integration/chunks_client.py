"""Text chunk retrieval with backend-first and local sample fallback."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class TextChunkRef:
    chunk_id: str
    page_no: int | None
    section: str | None
    content: str
    score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class ChunksClient:
    def __init__(self, *, api_base: str = "", samples_dir: Path | str = "data/samples", top_k: int = 5):
        self.api_base = (api_base or "").rstrip("/")
        self.samples_dir = Path(samples_dir)
        self.top_k = top_k

    def search(self, arxiv_id: str, query: str, *, timeout_s: float = 3.0) -> list[TextChunkRef]:
        if self.api_base:
            remote = self._search_remote(arxiv_id, query, timeout_s=timeout_s)
            if remote is not None:
                return remote
        return self._search_local(arxiv_id, query)

    def _search_remote(self, arxiv_id: str, query: str, *, timeout_s: float) -> list[TextChunkRef] | None:
        """POST the current API path, then retry the legacy path."""
        from .contracts import unwrap_api_response

        for path in ("/api/search/chunks", "/search/chunks"):
            url = f"{self.api_base}{path}"
            body = json.dumps({"arxiv_id": arxiv_id, "query": query, "top_k": self.top_k}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": "PaperMate-QA/0.2"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                items = unwrap_api_response(data)
                if isinstance(items, dict):
                    items = items.get("chunks", [])
                out: list[TextChunkRef] = []
                for c in (items or [])[: self.top_k]:
                    out.append(
                        TextChunkRef(
                            chunk_id=c.get("chunk_id") or c.get("sectionId") or "",
                            page_no=c.get("page_no", c.get("pageNumber")),
                            section=c.get("section") or c.get("sectionTitle"),
                            content=c.get("content") or c.get("quote") or "",
                            score=float(c.get("score", 0)),
                        )
                    )
                return out
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, TypeError):
                continue
        return None

    def _search_local(self, arxiv_id: str, query: str) -> list[TextChunkRef]:
        base = re.sub(r"v\d+$", "", arxiv_id)
        candidates = list(self.samples_dir.glob(f"*_{base}*.json")) + list(self.samples_dir.glob(f"*_{arxiv_id}*.json"))
        if not candidates:
            return []
        doc = json.loads(candidates[0].read_text(encoding="utf-8"))
        paras = doc.get("parse", {}).get("paragraphs_preview", [])
        if not paras and doc.get("structured"):
            s = doc["structured"]
            paras = [
                {
                    "para_id": f"{arxiv_id}:summary",
                    "page": 1,
                    "section": "summary",
                    "text": s.get("summary", ""),
                }
            ]
        tokens = set(re.findall(r"[a-z0-9]{3,}", query.lower()))
        scored: list[TextChunkRef] = []
        for p in paras:
            text = p.get("text", "")
            ptoks = set(re.findall(r"[a-z0-9]{3,}", text.lower()))
            score = len(tokens & ptoks) / max(len(tokens), 1)
            scored.append(
                TextChunkRef(
                    chunk_id=p.get("para_id", f"{arxiv_id}:chunk"),
                    page_no=p.get("page"),
                    section=p.get("section"),
                    content=text[:1200],
                    score=score,
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return [c for c in scored[: self.top_k] if c.score > 0 or c.content]
