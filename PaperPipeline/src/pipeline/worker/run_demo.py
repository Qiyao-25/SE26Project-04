#!/usr/bin/env python3
""" demo CLI: create → execute → success/failure with task_id + stage timing logs.

Run from PaperPipeline/:
  python -m worker.run_demo
or:
  set PYTHONPATH=src
  python -m pipeline.worker.run_demo
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Allow `python worker/run_demo.py` when cwd is .../pipeline
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline.schemas import TaskInput  # noqa: E402
from pipeline.worker.memory_queue import MemoryTaskQueue  # noqa: E402


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate memory-queue demo ()")
    parser.add_argument("--arxiv-id", default="1706.03762", help="Paper id (default P1)")
    parser.add_argument("--fail-stage", choices=["fetch", "parse", "summarize"], default=None)
    parser.add_argument("--also-fail-id", default="9999.99999", help="Enqueue a failing sample")
    parser.add_argument("--json-out", default="", help="Optional path to write last task JSON")
    args = parser.parse_args()

    _setup_logging()
    log = logging.getLogger("pipeline.demo")
    q = MemoryTaskQueue(max_attempts=3)

    # success task
    ok_in = TaskInput(arxiv_id=args.arxiv_id, pipeline_ver="v0")
    ok_task = q.create(ok_in)

    # failure task (P9)
    fail_in = TaskInput(arxiv_id=args.also_fail_id, pipeline_ver="v0")
    fail_task = q.create(fail_in)

    log.info("queue_pending=%s", q.pending_count())

    results = []
    # run success (optionally inject mid-stage fail on first task only via flag)
    results.append(q.run_once(simulate_fail_stage=args.fail_stage))
    results.append(q.run_once(simulate_fail_stage=None))

    # idempotent re-create of success paper
    again = q.create(TaskInput(arxiv_id=args.arxiv_id, pipeline_ver="v0"))
    log.info("idempotent_reuse task_id=%s status=%s", again.task_id, again.status.value)

    print("\n=== DEMO SUMMARY ===")
    for r in results:
        if not r:
            continue
        print(
            f"task_id={r.task_id} arxiv_id={r.input.arxiv_id} status={r.status.value} "
            f"stages={[ (t.stage, t.elapsed_s) for t in r.stage_timings ]}"
        )

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ok_task": ok_task.to_dict() if (ok_task := q.get(ok_task.task_id)) else None,
            "fail_task": fail_task.to_dict() if (fail_task := q.get(fail_task.task_id)) else None,
            "idempotent": again.to_dict(),
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}")

    # exit 0 if first demo task reached qa_ready and fail sample fetch_failed
    ok_rec = q.get(ok_task.task_id)
    fail_rec = q.get(fail_task.task_id)
    success = (
        ok_rec is not None
        and ok_rec.status.value == "qa_ready"
        and fail_rec is not None
        and fail_rec.status.value == "fetch_failed"
    )
    if args.fail_stage:
        success = ok_rec is not None and ok_rec.status.value.endswith("failed")
    print("RESULT:", "PASS" if success else "FAIL")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
