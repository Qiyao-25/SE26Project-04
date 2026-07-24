"""Field cleaning for crawled arXiv metadata ()."""

from __future__ import annotations

import re
from typing import Iterable

from .arxiv_client import PaperMeta

_SPACE = re.compile(r"\s+")
_VERSION = re.compile(r"v\d+$", re.I)
_PUNCT = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def clean_text(value: str) -> str:
    return _SPACE.sub(" ", (value or "").replace("\n", " ")).strip()


def normalize_arxiv_id(arxiv_id: str) -> str:
    aid = (arxiv_id or "").strip()
    aid = aid.rsplit("/", 1)[-1]
    return _VERSION.sub("", aid)


def normalize_title(title: str) -> str:
    value = clean_text(title).casefold()
    return _PUNCT.sub("", value)


def clean_paper(paper: PaperMeta) -> PaperMeta | None:
    """Return cleaned copy, or None if required fields missing."""
    arxiv_id = normalize_arxiv_id(paper.arxiv_id)
    title = clean_text(paper.title)
    abstract = clean_text(paper.abstract)
    authors = [clean_text(a) for a in paper.authors if clean_text(a)]
    categories = [clean_text(c) for c in paper.categories if clean_text(c)]
    if not arxiv_id or not title or not abstract:
        return None
    return PaperMeta(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        categories=categories,
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        published=paper.published,
        updated=paper.updated,
    )


def dedupe_by_id(papers: Iterable[PaperMeta]) -> list[PaperMeta]:
    seen: set[str] = set()
    out: list[PaperMeta] = []
    for p in papers:
        if p.arxiv_id in seen:
            continue
        seen.add(p.arxiv_id)
        out.append(p)
    return out


def dedupe_by_title(papers: Iterable[PaperMeta]) -> list[PaperMeta]:
    """Keep first paper per normalized title (secondary guard after arxiv_id)."""
    seen: set[str] = set()
    out: list[PaperMeta] = []
    for paper in papers:
        key = normalize_title(paper.title)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(paper)
    return out


def dedupe_papers(papers: Iterable[PaperMeta]) -> list[PaperMeta]:
    return dedupe_by_title(dedupe_by_id(papers))
