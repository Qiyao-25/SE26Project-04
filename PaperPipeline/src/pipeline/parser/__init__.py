"""Parser package:  stub +  real PDF parse."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .pdf_parse import Paragraph, ParseResult, ensure_pdf, extract_paragraphs, parse_pdf_file

__all__ = [
    "Chunk",
    "ParseOutput",
    "parse_pdf",
    "Paragraph",
    "ParseResult",
    "ensure_pdf",
    "extract_paragraphs",
    "parse_pdf_file",
]


@dataclass
class Chunk:
    chunk_id: str
    page: int
    section: str
    text: str


@dataclass
class ParseOutput:
    ok: bool
    degraded: bool = False
    chunks: list[Chunk] = field(default_factory=list)
    error: str | None = None


def parse_pdf(arxiv_id: str, pdf_path: str, *, fail: bool = False, sleep_s: float = 0.05) -> ParseOutput:
    """Stub for memory-queue demo ()."""
    time.sleep(sleep_s)
    if fail:
        return ParseOutput(ok=False, error="parse_failed: empty text")
    chunks = [
        Chunk(chunk_id=f"{arxiv_id}:c0", page=1, section="intro", text="Introduction stub paragraph."),
        Chunk(chunk_id=f"{arxiv_id}:c1", page=2, section="method", text="Method stub paragraph."),
    ]
    return ParseOutput(ok=True, chunks=chunks, degraded=False)
