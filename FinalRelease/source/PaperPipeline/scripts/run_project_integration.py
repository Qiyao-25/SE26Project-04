#!/usr/bin/env python3
"""Project integration smoke: local pipeline + optional live backend loop.

Usage (from PaperPipeline/):
  set PYTHONPATH=src
  python scripts/run_project_integration.py              # local only
  set PAPERMATE_API_BASE=http://127.0.0.1:8000
  python scripts/run_project_integration.py --with-backend
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipeline.crawler.arxiv_client import PaperMeta  # noqa: E402
from pipeline.crawler.ingest import ingest_papers  # noqa: E402
from pipeline.integration.backend_client import BackendClient  # noqa: E402
from pipeline.integration.contracts import paper_meta_to_backend  # noqa: E402
from pipeline.worker.backend_worker import BackendParseWorker  # noqa: E402


def _run_module(module: str) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", module],
        cwd=str(ROOT),
        env=env,
        check=False,
    )
    return int(proc.returncode)


def _local_checks() -> dict:
    demo = _run_module("pipeline.worker.run_demo")
    qa = _run_module("pipeline.qa.run_eval")
    return {"run_demo": demo == 0, "qa_eval": qa == 0}


def _backend_loop(api_base: str, arxiv_id: str) -> dict:
    client = BackendClient(api_base)
    out: dict = {"api_base": api_base, "arxiv_id": arxiv_id}
    health = client.health()
    out["health"] = health.get("status") if isinstance(health, dict) else str(health)

    meta = PaperMeta(
        arxiv_id=arxiv_id,
        title="Attention Is All You Need" if arxiv_id.startswith("1706.03762") else arxiv_id,
        authors=["Demo Author"],
        abstract="Integration smoke abstract for PaperMate pipeline.",
        categories=["cs.CL"],
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
    )
    report = ingest_papers(
        [meta],
        seed_path=ROOT / "data" / "seed_integration.json",
        failures_path=ROOT / "data" / "ingest_failures_integration.json",
        api_base=api_base,
    )
    out["ingest_mode"] = report.mode
    out["ingest_created"] = report.created
    out["ingest_updated"] = report.updated
    if report.mode != "api":
        out["ingest_message"] = report.message
        out["ok"] = False
        return out

    paper_id = client.find_paper_id_by_arxiv(arxiv_id)
    out["paper_id"] = paper_id
    if paper_id is None:
        out["ok"] = False
        out["error"] = "paper not found after batch"
        return out

    task = client.create_parse_task(paper_id, arxiv_id, force=True)
    out["task_id"] = task.get("task_id")
    out["task_status"] = task.get("status")

    worker = BackendParseWorker(
        client,
        ROOT / "data" / "worker_pdfs",
        html_dir=ROOT / "data" / "worker_html",
        max_pages=15,
        min_chars=200,
    )
    # Prefer processing the task we just created
    result = worker.process_task(task) if task.get("task_id") else worker.run_once()
    out["worker"] = result
    if result and result.get("status") == "succeeded":
        wiki = client.get_wiki(paper_id)
        out["wiki_summary_len"] = len((wiki or {}).get("summary") or "")
        out["qa_ready"] = (wiki or {}).get("qa_ready")
        chunks = client.search_chunks(query="attention", paper_id=paper_id, top_k=3)
        out["chunk_hits"] = len((chunks or {}).get("chunks") or [])
        out["ok"] = True
    else:
        out["ok"] = False
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate project integration smoke")
    parser.add_argument("--with-backend", action="store_true", help="Exercise live backend APIs")
    parser.add_argument("--api-base", default=os.environ.get("PAPERMATE_API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--arxiv-id", default="1706.03762")
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--out", default="data/integration_smoke.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    payload: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local": None,
        "backend": None,
    }

    ok = True
    if not args.skip_local:
        local = _local_checks()
        payload["local"] = local
        ok = ok and all(local.values())
        print("LOCAL:", local)

    if args.with_backend or os.environ.get("PAPERMATE_API_BASE"):
        try:
            backend = _backend_loop(args.api_base.rstrip("/"), args.arxiv_id)
        except Exception as exc:  # noqa: BLE001
            backend = {"ok": False, "error": str(exc), "api_base": args.api_base}
        payload["backend"] = backend
        ok = ok and bool(backend.get("ok"))
        print("BACKEND:", json.dumps(backend, ensure_ascii=False, indent=2))
    else:
        print("BACKEND: skipped (pass --with-backend or set PAPERMATE_API_BASE)")

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
