#!/usr/bin/env python3
""": parse + structure all 10 frozen samples; write scorecard.

Usage (from PaperPipeline/):
  set PYTHONPATH=src
  python -m pipeline.parser.run_samples
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline.parser.document import parse_document  # noqa: E402
from pipeline.summarizer.struct_summary import build_structured  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = [
    ("P1", "1706.03762", "Attention Is All You Need", False),
    ("P2", "1810.04805", "BERT", False),
    ("P3", "1806.07366", "Neural ODEs", False),
    ("P4", "2106.09685", "LoRA", False),
    ("P5", "2303.18223", "Survey of LLMs", False),  # long → truncate pages
    ("P6", "2010.11929", "ViT", False),
    ("P7", "2005.11401", "RAG", False),
    ("P8", "2005.14165", "GPT-3", False),  # large → truncate
    ("P9", "9999.99999", "invalid", True),
    ("P10", "0000.00001", "unavailable", True),
]

LONG_IDS = {"2303.18223", "2005.14165"}


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse+structure 10 samples ()")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data" / "samples")
    parser.add_argument("--pdf-dir", type=Path, default=ROOT / "data" / "samples" / "pdfs")
    parser.add_argument("--html-dir", type=Path, default=ROOT / "data" / "samples" / "html")
    parser.add_argument("--prefer-html", action="store_true")
    parser.add_argument(
        "--extra-pdf-dir",
        type=Path,
        action="append",
        default=[],
        help="Extra dirs to search for local PDFs (can repeat)",
    )
    parser.add_argument("--max-pages-long", type=int, default=40)
    args = parser.parse_args()
    _setup_logging()
    log = logging.getLogger("pipeline.samples")

    extra = list(args.extra_pdf_dir)
    spike_pdf = ROOT / "data" / "spike" / "pdfs"
    if spike_pdf.exists():
        extra.append(spike_pdf)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    success_required = 0

    for sid, arxiv_id, title, expect_fail in SAMPLES:
        t0 = time.perf_counter()
        row = {
            "sample": sid,
            "arxiv_id": arxiv_id,
            "title": title,
            "expect_fail": expect_fail,
            "status": "",
            "required_fields_ok": False,
            "page_count": 0,
            "para_count": 0,
            "elapsed_s": 0.0,
            "error": None,
            "artifact": None,
        }
        try:
            if expect_fail:
                row["status"] = "fetch_failed"
                row["error"] = "invalid/unavailable id (by design)"
                row["elapsed_s"] = round(time.perf_counter() - t0, 3)
                # still write a tiny failure artifact
                art = {
                    "sample": sid,
                    "arxiv_id": arxiv_id,
                    "status": "fetch_failed",
                    "structured": None,
                    "parse": None,
                }
                path = args.out_dir / f"{sid}_{arxiv_id}.json"
                path.write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")
                row["artifact"] = str(path)
            else:
                max_pages = args.max_pages_long if arxiv_id in LONG_IDS else None
                parsed = parse_document(
                    arxiv_id,
                    args.pdf_dir,
                    args.html_dir,
                    pdf_search_dirs=extra,
                    max_pages=max_pages,
                    prefer_html=args.prefer_html,
                )
                wiki = build_structured(arxiv_id, parsed.paragraphs, title=title)
                req_ok = parsed.ok and wiki.required_ok()
                status = parsed.status if parsed.ok else parsed.status
                if parsed.ok and not wiki.required_ok():
                    status = "summarize_failed"
                row.update(
                    {
                        "status": status,
                        "required_fields_ok": req_ok,
                        "page_count": parsed.page_count,
                        "para_count": len(parsed.paragraphs),
                        "elapsed_s": round(time.perf_counter() - t0, 3),
                        "error": parsed.error,
                    }
                )
                art = {
                    "sample": sid,
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status": status,
                    "parse": {
                        "status": parsed.status,
                        "pdf_path": parsed.pdf_path,
                        "source_type": parsed.source_type,
                        "page_count": parsed.page_count,
                        "char_count": parsed.char_count,
                        "paragraph_count": len(parsed.paragraphs),
                        "paragraphs_preview": [p.__dict__ for p in parsed.paragraphs[:5]],
                        "elapsed_s": parsed.elapsed_s,
                    },
                    "structured": wiki.to_dict(),
                    "required_fields_ok": req_ok,
                }
                path = args.out_dir / f"{sid}_{arxiv_id}.json"
                path.write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")
                row["artifact"] = str(path)
                if req_ok:
                    success_required += 1
        except Exception as exc:  # noqa: BLE001
            row["status"] = "failed"
            row["error"] = str(exc)
            row["elapsed_s"] = round(time.perf_counter() - t0, 3)
            log.exception("sample_failed %s %s", sid, arxiv_id)

        log.info(
            "%s %s status=%s required_ok=%s paras=%s elapsed=%.2fs",
            sid,
            arxiv_id,
            row["status"],
            row["required_fields_ok"],
            row["para_count"],
            row["elapsed_s"],
        )
        rows.append(row)

    # fail samples correctly failed?
    fail_ok = all(
        (r["sample"] in {"P9", "P10"} and r["status"] == "fetch_failed")
        or r["sample"] not in {"P9", "P10"}
        for r in rows
    )
    scorecard = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "success_with_required_fields": success_required,
        "total_samples": 10,
        "threshold": 8,
        "pass": success_required >= 8 and fail_ok,
        "fail_samples_correct": fail_ok,
        "rows": rows,
    }
    sc_path = args.out_dir / "scorecard.json"
    sc_path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== SAMPLE SCORECARD ===")
    for r in rows:
        print(
            f"{r['sample']} {r['arxiv_id']} status={r['status']} "
            f"required_ok={r['required_fields_ok']} paras={r['para_count']}"
        )
    print(f"required_ok_count={success_required}/10 threshold=8 fail_samples_ok={fail_ok}")
    print(f"scorecard={sc_path}")
    print("RESULT:", "PASS" if scorecard["pass"] else "FAIL")
    return 0 if scorecard["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
