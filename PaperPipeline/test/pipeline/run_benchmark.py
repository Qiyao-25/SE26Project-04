#!/usr/bin/env python3
"""H087 — benchmark crawl/parse/summarize/qa stage timings."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline.crawler import fetch_paper  # noqa: E402
from pipeline.parser import parse_pdf  # noqa: E402
from pipeline.summarizer import summarize  # noqa: E402
from pipeline.integration.chunks_client import ChunksClient  # noqa: E402
from pipeline.qa.service import QAService  # noqa: E402


def _root() -> Path:
    return Path(__file__).resolve().parents[2]  # PaperPipeline


def _bench_one(arxiv_id: str, *, samples_dir: Path, question: str) -> dict:
    stages: list[dict] = []

    t0 = time.perf_counter()
    fetch = fetch_paper(arxiv_id)
    stages.append({"stage": "fetch", "elapsed_s": round(time.perf_counter() - t0, 4), "ok": fetch.ok})
    if not fetch.ok:
        return {"arxiv_id": arxiv_id, "ok": False, "stages": stages}

    t0 = time.perf_counter()
    parsed = parse_pdf(arxiv_id, fetch.pdf_path)
    stages.append({"stage": "parse", "elapsed_s": round(time.perf_counter() - t0, 4), "ok": parsed.ok})
    if not parsed.ok:
        return {"arxiv_id": arxiv_id, "ok": False, "stages": stages}

    t0 = time.perf_counter()
    summ = summarize(arxiv_id, parsed.chunks, fetch.abstract)
    stages.append({"stage": "summarize", "elapsed_s": round(time.perf_counter() - t0, 4), "ok": summ.ok})
    if not summ.ok:
        return {"arxiv_id": arxiv_id, "ok": False, "stages": stages}

    t0 = time.perf_counter()
    qa = QAService(ChunksClient(samples_dir=samples_dir))
    ans = qa.ask(arxiv_id, question)
    stages.append({"stage": "qa", "elapsed_s": round(time.perf_counter() - t0, 4), "ok": ans.ok})

    total = round(sum(s["elapsed_s"] for s in stages), 4)
    return {"arxiv_id": arxiv_id, "ok": ans.ok, "stages": stages, "total_s": total}


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate pipeline benchmark (H087)")
    parser.add_argument("--out", default="test/pipeline/benchmark.json")
    args = parser.parse_args()

    root = _root()
    samples = root / "data/samples"
    out_path = root / args.out

    papers = [
        ("1706.03762", "Transformer 是否依赖 CNN/RNN？"),
        ("1810.04805", "BERT 预训练任务有哪些？"),
        ("2005.11401", "RAG 结合哪两类能力？"),
    ]

    runs = []
    for arxiv_id, q in papers:
        runs.append(_bench_one(arxiv_id, samples_dir=samples, question=q))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "no-key-sample",
        "papers": runs,
        "summary": {
            "count": len(runs),
            "ok": sum(1 for r in runs if r["ok"]),
            "avg_total_s": round(
                sum(r.get("total_s", 0) for r in runs) / max(len(runs), 1),
                4,
            ),
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"benchmark ok={payload['summary']['ok']}/{payload['summary']['count']}")
    print(f"wrote {out_path}")
    return 0 if payload["summary"]["ok"] == len(runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
