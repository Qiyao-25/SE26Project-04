#!/usr/bin/env python3
"""H088 — 3-paper full pipeline demo (crawl→parse→wiki→qa), no-key mode."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline.schemas import TaskInput  # noqa: E402
from pipeline.worker.memory_queue import MemoryTaskQueue  # noqa: E402
from pipeline.integration.chunks_client import ChunksClient  # noqa: E402
from pipeline.qa.service import QAService  # noqa: E402


def _root() -> Path:
    return Path(__file__).resolve().parents[2]  # PaperPipeline


DEMO_PAPERS = [
    {"sample": "P1", "arxiv_id": "1706.03762", "question": "Multi-Head Attention 的作用？"},
    {"sample": "P2", "arxiv_id": "1810.04805", "question": "BERT 预训练任务有哪些？"},
    {"sample": "P7", "arxiv_id": "2005.11401", "question": "RAG 结合哪两类能力？"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate 3-paper demo (H088)")
    parser.add_argument("--out-dir", default="data/demo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = _root()
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    q = MemoryTaskQueue()
    qa = QAService(ChunksClient(samples_dir=root / "data/samples"))
    archive: list[dict] = []

    for paper in DEMO_PAPERS:
        rec = q.create(TaskInput(arxiv_id=paper["arxiv_id"], pipeline_ver="v0"))
        rec = q.execute(rec.task_id)
        ans = qa.ask(paper["arxiv_id"], paper["question"])
        item = {
            "sample": paper["sample"],
            "arxiv_id": paper["arxiv_id"],
            "pipeline": rec.to_dict(),
            "qa": ans.to_dict(),
        }
        archive.append(item)
        (out_dir / f"{paper['sample']}_{paper['arxiv_id']}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "no-key-sample",
        "papers": len(archive),
        "pipeline_ok": sum(1 for a in archive if a["pipeline"]["status"] == "qa_ready"),
        "qa_ok": sum(1 for a in archive if a["qa"]["ok"]),
        "items": archive,
    }
    summary_path = out_dir / "demo_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"demo pipeline_ok={summary['pipeline_ok']}/3 qa_ok={summary['qa_ok']}/3")
    print(f"wrote {summary_path}")
    return 0 if summary["pipeline_ok"] == 3 and summary["qa_ok"] == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
