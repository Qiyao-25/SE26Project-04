#!/usr/bin/env python3
"""Run the database-backed PaperMate parse worker.

Examples from the PaperPipeline directory:
  python -m pipeline.worker.run_backend_worker --once
  python -m pipeline.worker.run_backend_worker --api-base http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline.integration.backend_client import BackendClient  # noqa: E402
from pipeline.worker.backend_worker import BackendParseWorker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate database-backed PDF parse worker")
    parser.add_argument("--api-base", default=os.environ.get("PAPERMATE_API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("data/worker_pdfs"))
    parser.add_argument("--html-dir", type=Path, default=Path("data/worker_html"))
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--max-tasks", type=int, default=0, help="0 means run continuously")
    parser.add_argument("--stale-timeout", type=int, default=900, help="seconds before a running task is stale")
    parser.add_argument("--recover-interval", type=float, default=60.0, help="seconds between stale task recovery checks")
    parser.add_argument("--max-pages", type=int, default=0, help="0 means no page limit")
    parser.add_argument("--min-chars", type=int, default=500)
    parser.add_argument("--prefer-html", action="store_true", help="try ar5iv HTML before PDF")
    parser.add_argument("--once", action="store_true", help="process at most one queued task")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    worker = BackendParseWorker(
        BackendClient(args.api_base),
        args.pdf_dir,
        max_pages=args.max_pages or None,
        min_chars=args.min_chars,
        html_dir=args.html_dir,
        prefer_html=args.prefer_html,
    )
    try:
        recovered = worker.client.recover_stale_tasks(args.stale_timeout)
        logging.info("stale_tasks_recovered count=%s", recovered.get("recovered", 0))
    except Exception:  # noqa: BLE001
        logging.exception("stale_task_recovery_failed")

    processed = 0
    last_recovery = time.monotonic()
    while True:
        if time.monotonic() - last_recovery >= max(args.recover_interval, 1.0):
            try:
                recovered = worker.client.recover_stale_tasks(args.stale_timeout)
                logging.info("stale_tasks_recovered count=%s", recovered.get("recovered", 0))
            except Exception:  # noqa: BLE001
                logging.exception("stale_task_recovery_failed")
            last_recovery = time.monotonic()
        result = worker.run_once()
        if result is not None:
            processed += 1
            if result["status"] == "failed":
                logging.getLogger("pipeline.backend_worker").error("worker_result=%s", result)
            if args.once:
                return 1 if result["status"] == "failed" else 0
            if args.max_tasks and processed >= args.max_tasks:
                return 1 if result["status"] == "failed" else 0
            continue
        if args.once:
            logging.info("no queued parse task")
            return 0
        time.sleep(max(args.poll_interval, 0.2))


if __name__ == "__main__":
    raise SystemExit(main())
