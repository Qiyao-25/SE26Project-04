#!/usr/bin/env python3
"""H047/H048 crawl CLI: keyword fetch → clean → ≥N seed + optional API ingest.

Usage (from PaperPipeline/):
  set PYTHONPATH=src
  python -m pipeline.crawler.run_crawl --target 100
"""

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

from pipeline.crawler.arxiv_client import ArxivClient  # noqa: E402
from pipeline.crawler.clean import clean_paper, dedupe_by_id  # noqa: E402
from pipeline.crawler.ingest import ingest_papers  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]  # PaperPipeline
DEFAULT_SEED = ROOT / "data" / "seed.json"
DEFAULT_FAIL = ROOT / "data" / "ingest_failures.json"
DEFAULT_REPORT = ROOT / "data" / "crawl_report.json"

DEFAULT_QUERIES = [
    "all:transformer",
    "all:bert language",
    "all:large language model",
    "all:retrieval augmented",
    "cat:cs.CL",
]


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def crawl_until(
    client: ArxivClient,
    *,
    target: int,
    page_size: int,
    queries: list[str],
) -> tuple[list, list[dict]]:
    collected = []
    drop_log: list[dict] = []
    for q in queries:
        start = 0
        while len(collected) < target:
            need = min(page_size, target - len(collected) + 10)
            logging.getLogger("pipeline.crawl").info(
                "query=%s start=%s max_results=%s have=%s", q, start, need, len(collected)
            )
            try:
                batch = client.search(search_query=q, start=start, max_results=need)
            except Exception as exc:  # noqa: BLE001
                drop_log.append({"query": q, "start": start, "error": str(exc)})
                break
            if not batch:
                break
            for raw in batch:
                cleaned = clean_paper(raw)
                if cleaned is None:
                    drop_log.append(
                        {
                            "query": q,
                            "arxiv_id": raw.arxiv_id,
                            "error": "clean_rejected_missing_fields",
                        }
                    )
                    continue
                collected.append(cleaned)
            collected = dedupe_by_id(collected)
            start += len(batch)
            if len(batch) < need:
                break
        if len(collected) >= target:
            break
    return collected[: target] if len(collected) > target else collected, drop_log


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate crawl ≥N papers (H047/H048)")
    parser.add_argument("--target", type=int, default=100, help="Minimum cleaned papers")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--min-interval", type=float, default=3.0, help="arXiv courtesy delay")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--failures", type=Path, default=DEFAULT_FAIL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--api-base", default="", help="Override PAPERMATE_API_BASE")
    args = parser.parse_args()

    _setup_logging()
    log = logging.getLogger("pipeline.crawl")
    client = ArxivClient(timeout_s=args.timeout, min_interval_s=args.min_interval)

    papers, drop_log = crawl_until(
        client,
        target=args.target,
        page_size=args.page_size,
        queries=DEFAULT_QUERIES,
    )
    log.info("cleaned_unique=%s target=%s client_failures=%s", len(papers), args.target, len(client.failures))

    args.failures.parent.mkdir(parents=True, exist_ok=True)
    fail_doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "http_failures": [
            {"query": f.query, "error": f.error, "attempt": f.attempt} for f in client.failures
        ],
        "clean_drops": drop_log,
    }
    args.failures.write_text(json.dumps(fail_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    ingest = ingest_papers(
        papers,
        seed_path=args.seed,
        failures_path=args.failures,
        api_base=args.api_base or None,
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "cleaned_count": len(papers),
        "ingest_mode": ingest.mode,
        "ingest_message": ingest.message,
        "seed_path": ingest.seed_path,
        "failures_path": str(args.failures),
        "sample_ids": [p.arxiv_id for p in papers[:5]],
        "pass_h047": len(papers) >= min(10, args.target) or len(papers) > 0,
        "pass_h048_seed": len(papers) >= args.target and args.seed.exists(),
        "pass_h048_api": ingest.mode == "api",
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== CRAWL SUMMARY ===")
    print(f"cleaned={len(papers)} target={args.target}")
    print(f"ingest_mode={ingest.mode}")
    print(f"seed={ingest.seed_path}")
    print(f"failures={args.failures}")
    print(f"message={ingest.message}")
    ok = report["pass_h048_seed"]
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
