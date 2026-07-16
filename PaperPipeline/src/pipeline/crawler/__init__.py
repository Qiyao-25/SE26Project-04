"""Crawler package: stub (H038) + real arXiv client (H047)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .arxiv_client import ArxivClient, PaperMeta
from .clean import clean_paper, clean_text, dedupe_by_id, normalize_arxiv_id

__all__ = [
    "ArxivClient",
    "PaperMeta",
    "FetchOutput",
    "fetch_paper",
    "clean_paper",
    "clean_text",
    "dedupe_by_id",
    "normalize_arxiv_id",
]


@dataclass
class FetchOutput:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    pdf_path: str
    ok: bool
    error: str | None = None


def fetch_paper(arxiv_id: str, *, fail: bool = False, sleep_s: float = 0.05) -> FetchOutput:
    """Stub used by memory-queue demo (H038). Real bulk crawl: run_crawl.py."""
    time.sleep(sleep_s)
    if fail or arxiv_id in {"9999.99999", "0000.00001"}:
        return FetchOutput(
            arxiv_id=arxiv_id,
            title="",
            authors=[],
            abstract="",
            pdf_path="",
            ok=False,
            error="fetch_failed: invalid or unavailable id",
        )
    return FetchOutput(
        arxiv_id=arxiv_id,
        title=f"Stub title for {arxiv_id}",
        authors=["Demo Author"],
        abstract="Stub abstract for pipeline skeleton demo.",
        pdf_path=f"data/samples/{arxiv_id}.pdf",
        ok=True,
    )
