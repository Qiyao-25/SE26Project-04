"""Backfill local PDF cache for papers already in the database.

Usage (from FinalRelease/source/backend):
  python -m scripts.sync_paper_pdfs
  python -m scripts.sync_paper_pdfs --limit 100 --delay 0.5
"""

from __future__ import annotations

import argparse
import json
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_engine_for
from app.service.pdf_stream import pdf_cache_stats, sync_missing_paper_pdfs


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync missing paper PDFs into local storage")
    parser.add_argument("--limit", type=int, default=50, help="Max papers to sync this run")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay seconds between downloads")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()

    with Session(create_engine_for(settings)) as session:
        before = pdf_cache_stats(session, settings)
        print("before:", json.dumps(before, ensure_ascii=False))
        result = sync_missing_paper_pdfs(
            session,
            limit=args.limit,
            delay_s=args.delay,
            settings=settings,
        )
        after = pdf_cache_stats(session, settings)
        print("result:", json.dumps(result, ensure_ascii=False, indent=2))
        print("after:", json.dumps(after, ensure_ascii=False))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
