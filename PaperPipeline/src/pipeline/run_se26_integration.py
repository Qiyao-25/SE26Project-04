#!/usr/bin/env python3
"""SE26 联调：PaperPipeline 已完成能力 → backend（入库→解析→Wiki→chunks）。

先启动 backend（uvicorn app.main:app --host 127.0.0.1 --port 8000），再执行：

  cd SE26Project-04/PaperPipeline
  $env:PYTHONPATH="src"
  $env:PAPERMATE_API_BASE="http://127.0.0.1:8000"
  python -m pipeline.run_se26_integration --arxiv-id 1706.03762
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline.crawler.arxiv_client import ArxivClient
from pipeline.integration.backend_client import BackendClient
from pipeline.integration.contracts import paper_meta_to_backend
from pipeline.worker.backend_worker import BackendParseWorker

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="SE26 PaperPipeline ↔ backend integration")
    parser.add_argument("--api-base", default=os.environ.get("PAPERMATE_API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--arxiv-id", default="1706.03762", help="样例论文（默认 P1 Transformer）")
    parser.add_argument("--pdf-dir", type=Path, default=ROOT / "data" / "worker_pdfs")
    parser.add_argument("--html-dir", type=Path, default=ROOT / "data" / "worker_html")
    parser.add_argument("--max-pages", type=int, default=25)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "integration" / "se26_last_run.json")
    parser.add_argument("--skip-parse", action="store_true", help="仅入库，不跑 Worker")
    parser.add_argument("--prefer-html", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    log = logging.getLogger("se26.integration")
    client = BackendClient(args.api_base, timeout_s=90.0)
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": args.api_base,
        "arxiv_id": args.arxiv_id,
        "steps": {},
    }

    try:
        health = client.health()
        report["steps"]["health"] = {"ok": True, "data": health}
        log.info("health ok")
    except Exception as exc:  # noqa: BLE001
        report["steps"]["health"] = {"ok": False, "error": str(exc)}
        log.error("backend 不可达: %s", exc)
        _write(args.out, report)
        return 1

    try:
        meta = ArxivClient(timeout_s=30.0, min_interval_s=0.5).fetch_by_id(args.arxiv_id)
        payload = [paper_meta_to_backend(meta)]
        upsert = client.batch_upsert_papers(payload)
        paper_id = client.find_paper_id_by_arxiv(meta.arxiv_id)
        report["steps"]["ingest"] = {
            "ok": paper_id is not None,
            "upsert": upsert,
            "paper_id": paper_id,
            "arxiv_id": meta.arxiv_id,
        }
        log.info("ingest paper_id=%s arxiv_id=%s upsert=%s", paper_id, meta.arxiv_id, upsert)
    except Exception as exc:  # noqa: BLE001
        report["steps"]["ingest"] = {"ok": False, "error": str(exc)}
        log.exception("ingest failed")
        _write(args.out, report)
        return 1

    if paper_id is None:
        report["steps"]["ingest"]["error"] = "无法解析 paper_id"
        _write(args.out, report)
        return 1

    if args.skip_parse:
        report["ok"] = True
        _write(args.out, report)
        print("RESULT: PASS (ingest only)")
        return 0

    try:
        task = client.create_parse_task(paper_id, meta.arxiv_id, force=True)
        report["steps"]["parse_task"] = {"ok": True, "task": task}
        log.info("parse_task id=%s status=%s", task.get("task_id"), task.get("status"))
    except Exception as exc:  # noqa: BLE001
        report["steps"]["parse_task"] = {"ok": False, "error": str(exc)}
        log.exception("create_parse_task failed")
        _write(args.out, report)
        return 1

    try:
        worker = BackendParseWorker(
            client,
            args.pdf_dir,
            max_pages=args.max_pages,
            html_dir=args.html_dir,
            prefer_html=args.prefer_html,
        )
        result = worker.process_task(task)
        report["steps"]["worker"] = {"ok": result.get("status") == "succeeded", "result": result}
        log.info("worker result=%s", result)
        if result.get("status") != "succeeded":
            _write(args.out, report)
            return 1
    except Exception as exc:  # noqa: BLE001
        report["steps"]["worker"] = {"ok": False, "error": str(exc)}
        log.exception("worker failed")
        _write(args.out, report)
        return 1

    try:
        wiki = client.get_wiki(paper_id)
        chunks_resp = client.search_chunks(query="attention", paper_id=paper_id, top_k=3)
        chunk_items = []
        if isinstance(chunks_resp, dict):
            chunk_items = chunks_resp.get("chunks") or chunks_resp.get("items") or []
        elif isinstance(chunks_resp, list):
            chunk_items = chunks_resp
        report["steps"]["wiki"] = {
            "ok": bool(wiki.get("summary")),
            "parse_status": wiki.get("parse_status"),
            "chunk_count": wiki.get("chunk_count"),
            "qa_ready": wiki.get("qa_ready"),
            "summary_preview": (wiki.get("summary") or "")[:180],
        }
        report["steps"]["search_chunks"] = {
            "ok": True,
            "n": len(chunk_items),
            "sample": chunk_items[:1],
        }
        log.info(
            "wiki parse_status=%s chunk_count=%s qa_ready=%s search_hits=%s",
            wiki.get("parse_status"),
            wiki.get("chunk_count"),
            wiki.get("qa_ready"),
            len(chunk_items),
        )
    except Exception as exc:  # noqa: BLE001
        report["steps"]["wiki"] = {"ok": False, "error": str(exc)}
        log.exception("wiki/chunks failed")
        _write(args.out, report)
        return 1

    ok = all(step.get("ok") for step in report["steps"].values() if isinstance(step, dict) and "ok" in step)
    report["ok"] = ok
    _write(args.out, report)
    print("RESULT:", "PASS" if ok else "FAIL")
    print(f"wrote {args.out}")
    return 0 if ok else 1


def _write(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
