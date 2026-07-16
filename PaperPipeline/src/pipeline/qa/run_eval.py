#!/usr/bin/env python3
"""H067/H068 — run 20 QA questions with citation validation (no-key sample mode)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline.integration.config import IntegrationConfig  # noqa: E402
from pipeline.integration.chunks_client import ChunksClient  # noqa: E402
from pipeline.qa.service import QAService  # noqa: E402


def _root() -> Path:
    # .../PaperPipeline/src/pipeline/qa/run_eval.py -> PaperPipeline
    return Path(__file__).resolve().parents[3]


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate QA eval (H067/H068)")
    parser.add_argument("--questions", default="data/qa/questions.json")
    parser.add_argument("--out", default="test/pipeline/qa_results.json")
    args = parser.parse_args()

    root = _root()
    cfg = IntegrationConfig.from_env()
    samples = root / cfg.samples_dir
    questions_path = root / args.questions
    out_path = root / args.out

    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    chunks = ChunksClient(api_base=cfg.api_base, samples_dir=samples)
    qa = QAService(chunks)

    results = []
    pass_count = 0
    for q in questions:
        paper_ok = q.get("kind") != "reject"
        res = qa.ask(q["arxiv_id"], q["question"], paper_available=paper_ok)
        expect_ok = q.get("kind") != "reject"
        expect_reject = q.get("kind") == "reject"
        passed = (res.ok and expect_ok) or (res.rejected and expect_reject)
        if passed:
            pass_count += 1
        entry = {
            "id": q["id"],
            "sample": q.get("sample"),
            "arxiv_id": q["arxiv_id"],
            "question": q["question"],
            "kind": q.get("kind"),
            "expect_ok": expect_ok,
            "passed": passed,
            "result": res.to_dict(),
        }
        if res.ok and res.citations:
            entry["ui_qa"] = res.to_ui(paper_id=q.get("sample") or q["arxiv_id"])
        results.append(entry)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": cfg.qa_mode,
        "api_base": cfg.api_base or None,
        "total": len(questions),
        "passed": pass_count,
        "pass_rate": round(pass_count / max(len(questions), 1), 4),
        "results": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"QA eval: {pass_count}/{len(questions)} passed")
    print(f"wrote {out_path}")
    # H068: ≥18/20 on answerable; reject cases must refuse
    return 0 if pass_count >= 18 else 1


if __name__ == "__main__":
    raise SystemExit(main())
