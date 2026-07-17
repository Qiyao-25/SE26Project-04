"""H048 ingest: POST /api/papers/batch (PaperUpsert list), else local seed.json."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..integration.contracts import paper_meta_to_backend, unwrap_api_response
from .arxiv_client import PaperMeta

logger = logging.getLogger("pipeline.ingest")


@dataclass
class IngestReport:
    mode: str  # "api" | "local_seed"
    attempted: int
    succeeded: int
    failed: int
    seed_path: str | None
    api_base: str | None
    failures: list[dict[str, Any]]
    message: str
    created: int = 0
    updated: int = 0


def ingest_papers(
    papers: list[PaperMeta],
    *,
    seed_path: Path,
    failures_path: Path,
    api_base: str | None = None,
    timeout_s: float = 10.0,
) -> IngestReport:
    api_base = (api_base or os.environ.get("PAPERMATE_API_BASE") or "").rstrip("/")
    seed_payload = [p.to_dict() for p in papers]
    # Backend expects list[PaperUpsert] with AuthorInput{name}
    api_payload = [paper_meta_to_backend(p) for p in papers]

    if api_base:
        ok, fails, detail, created, updated = _post_batch(api_base, api_payload, timeout_s=timeout_s)
        if ok:
            _write_seed(seed_path, seed_payload, source="api_mirror")
            return IngestReport(
                mode="api",
                attempted=len(api_payload),
                succeeded=len(api_payload) - len(fails),
                failed=len(fails),
                seed_path=str(seed_path),
                api_base=api_base,
                failures=fails,
                message=detail,
                created=created,
                updated=updated,
            )
        logger.warning("api_ingest_failed fallback_to_seed detail=%s", detail)

    _write_seed(seed_path, seed_payload, source="local_fallback")
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    crawl_failures: list = []
    if failures_path.exists():
        try:
            crawl_failures = json.loads(failures_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            crawl_failures = []
    return IngestReport(
        mode="local_seed",
        attempted=len(seed_payload),
        succeeded=len(seed_payload),
        failed=0,
        seed_path=str(seed_path),
        api_base=api_base or None,
        failures=crawl_failures if isinstance(crawl_failures, list) else [],
        message=(
            "backend 入库不可用：已写本地 seed.json。"
            "设置 PAPERMATE_API_BASE 后重跑 → POST /api/papers/batch。"
        ),
    )


def _write_seed(path: Path, papers: list[dict], *, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "count": len(papers),
        "papers": papers,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("seed_written path=%s count=%s source=%s", path, len(papers), source)


def _post_batch(
    api_base: str, papers: list[dict], *, timeout_s: float
) -> tuple[bool, list[dict], str, int, int]:
    """POST /api/papers/batch — body is a JSON array of PaperUpsert (backend contract)."""
    url = f"{api_base}/api/papers/batch"
    body = json.dumps(papers).encode("utf-8")  # raw list, not {"papers": ...}
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "PaperMate-Ingest/0.2"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            created = updated = 0
            try:
                data = unwrap_api_response(json.loads(raw))
                if isinstance(data, dict):
                    created = int(data.get("created") or 0)
                    updated = int(data.get("updated") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            return True, [], f"HTTP {resp.status}: {raw[:200]}", created, updated
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:300]
        return False, [{"error": f"HTTP {exc.code}", "body": err_body}], str(exc), 0, 0
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, [{"error": str(exc)}], str(exc), 0, 0
