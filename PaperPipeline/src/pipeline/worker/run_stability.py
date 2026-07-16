#!/usr/bin/env python3
"""H077/H078 — success / timeout / failure scenarios + task log export."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline.schemas import TaskInput  # noqa: E402
from pipeline.worker.stability import StableTaskQueue  # noqa: E402


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate stability demo (H077/H078)")
    parser.add_argument("--out", default="data/stability/scenarios.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = _root()
    log_dir = root / "data/logs"
    out_path = root / args.out

    q = StableTaskQueue(max_attempts=3, log_dir=log_dir)

    scenarios = [
        ("success", TaskInput(arxiv_id="1706.03762", pipeline_ver="v0"), None),
        ("fetch_failure", TaskInput(arxiv_id="9999.99999", pipeline_ver="v0"), "fetch"),
        ("parse_retry_recovery", TaskInput(arxiv_id="1706.03762", pipeline_ver="v0", force=True), "parse"),
    ]

    results = []
    for name, tin, fail in scenarios:
        rec = q.run_scenario(name, tin, simulate_fail_stage=fail)
        log_file = log_dir / f"{rec.task_id}.json"
        results.append(
            {
                "scenario": name,
                "task_id": rec.task_id,
                "status": rec.status.value,
                "attempts": rec.attempts,
                "stage_timings": [t.__dict__ for t in rec.stage_timings],
                "log_path": str(log_file.relative_to(root)) if log_file.exists() else None,
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenarios": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")

    ok = (
        results[0]["status"] == "qa_ready"
        and results[1]["status"] == "fetch_failed"
        and results[2]["status"] == "qa_ready"
        and results[2]["attempts"] >= 2
    )
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
