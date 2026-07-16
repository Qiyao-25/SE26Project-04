"""H037 summarizer stub — summary / concept / methods."""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..parser import Chunk


@dataclass
class SummarizeOutput:
    ok: bool
    summary: str = ""
    concept: str = ""
    methods: str = ""
    error: str | None = None


def summarize(arxiv_id: str, chunks: list[Chunk], abstract: str, *, fail: bool = False, sleep_s: float = 0.02) -> SummarizeOutput:
    time.sleep(sleep_s)
    if fail:
        return SummarizeOutput(ok=False, error="summarize_failed: empty fields")
    body = " ".join(c.text for c in chunks)
    return SummarizeOutput(
        ok=True,
        summary=f"[{arxiv_id}] {abstract[:120]}",
        concept=f"Key concepts from chunks: {body[:160]}",
        methods=f"Methods sketched from {len(chunks)} chunks.",
    )
