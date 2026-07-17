""" ingest: try member-C API (ORM-aligned), else write/merge local seed.json."""

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


def ingest_papers(
    papers: list[PaperMeta],
    *,
    seed_path: Path,
    failures_path: Path,
    api_base: str | None = None,
    timeout_s: float = 10.0,
) -> IngestReport:
    api_base = (api_base or os.environ.get("PAPERMATE_API_BASE") or "").rstrip("/")
    # Local seed keeps crawler-native shape for offline demos
    seed_payload = [p.to_dict() for p in papers]
    # API payload matches backend entities.Paper (+ nested authors)
    api_payload = [paper_meta_to_backend(p) for p in papers]

    if api_base:
        ok, fails, detail = _post_batch(api_base, api_payload, timeout_s=timeout_s)
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
            )
        logger.warning("api_ingest_failed fallback_to_seed detail=%s", detail)

    _write_seed(seed_path, seed_payload, source="local_fallback")
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    crawl_failures = []
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
            "C 入库 API 未配置或不可用：已写入本地 seed.json。"
            "设置 PAPERMATE_API_BASE 后重跑；API 体已对齐 entities.Paper。"
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


def _post_batch(api_base: str, papers: list[dict], *, timeout_s: float) -> tuple[bool, list[dict], str]:
    """POST /api/papers/batch — body papers[] aligned with backend API."""
    url = f"{api_base}/api/papers/batch"
    body = json.dumps({"papers": papers}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "PaperMate-Ingest/0.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                unwrap_api_response(json.loads(raw))
            except json.JSONDecodeError:
                pass
            return True, [], f"HTTP {resp.status}: {raw[:200]}"
    except urllib.error.HTTPError as exc:
        return False, [{"error": f"HTTP {exc.code}", "body": exc.read().decode("utf-8", errors="replace")[:300]}], str(exc)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, [{"error": str(exc)}], str(exc)
