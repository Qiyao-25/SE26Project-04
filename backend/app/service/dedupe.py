"""Title / arXiv ID normalization helpers for crawl and upsert dedup."""

from __future__ import annotations

import re

_SPACE = re.compile(r"\s+")
_VERSION = re.compile(r"v\d+$", re.I)
_PUNCT = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def normalize_arxiv_id(arxiv_id: str) -> str:
    aid = (arxiv_id or "").strip()
    aid = aid.rsplit("/", 1)[-1]
    return _VERSION.sub("", aid)


def normalize_title(title: str) -> str:
    """Casefold + strip punctuation/whitespace for near-duplicate title matching.

    Upsert rule: identical normalized titles reuse the existing Paper row
    (even when arXiv IDs differ). Primary key remains arxiv_id when present.
    """
    value = _SPACE.sub(" ", (title or "").replace("\n", " ")).strip().casefold()
    value = _PUNCT.sub("", value)
    return value


__all__ = ["normalize_arxiv_id", "normalize_title"]
