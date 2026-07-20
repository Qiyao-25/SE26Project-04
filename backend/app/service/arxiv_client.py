"""Minimal arXiv Atom API client for subscription sync / scheduled crawl."""

from __future__ import annotations

import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger("papermate.arxiv")

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


@dataclass
class ArxivPaperMeta:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    pdf_url: str
    abs_url: str
    published: str = ""


class ArxivClient:
    def __init__(self, *, timeout_s: float = 20.0, min_interval_s: float = 3.0, max_retries: int = 3) -> None:
        self.timeout_s = timeout_s
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        gap = time.perf_counter() - self._last_request_at
        if gap < self.min_interval_s:
            time.sleep(self.min_interval_s - gap)

    def _http_get(self, url: str) -> bytes:
        self._throttle()
        req = urllib.request.Request(url, headers={"User-Agent": "PaperMate-Backend/0.2 (course demo)"})
        attempt = 0
        backoff = 1.0
        while True:
            attempt += 1
            try:
                self._last_request_at = time.perf_counter()
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.read()
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                logger.warning("arxiv_http_error attempt=%s err=%s", attempt, exc)
                if attempt >= self.max_retries:
                    raise
                time.sleep(backoff)
                backoff *= 2

    def search(self, *, search_query: str, max_results: int = 5, sort_by: str = "submittedDate") -> list[ArxivPaperMeta]:
        params = urllib.parse.urlencode(
            {
                "search_query": search_query,
                "start": 0,
                "max_results": max_results,
                "sortBy": sort_by,
                "sortOrder": "descending",
            }
        )
        return _parse_feed(self._http_get(f"{ARXIV_API}?{params}"))


def _parse_feed(xml_bytes: bytes) -> list[ArxivPaperMeta]:
    root = ET.fromstring(xml_bytes)
    papers: list[ArxivPaperMeta] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        raw_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        arxiv_id = re.sub(r"v\d+$", "", raw_id.rsplit("/abs/", 1)[-1])
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").split())
        abstract = " ".join((entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").split())
        authors = [
            a.findtext("atom:name", default="", namespaces=ATOM_NS) or ""
            for a in entry.findall("atom:author", ATOM_NS)
        ]
        categories = [c.get("term", "") for c in entry.findall("atom:category", ATOM_NS)]
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS) or ""
        papers.append(
            ArxivPaperMeta(
                arxiv_id=arxiv_id,
                title=title,
                authors=[a for a in authors if a],
                abstract=abstract,
                categories=[c for c in categories if c],
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                abs_url=f"https://arxiv.org/abs/{arxiv_id}",
                published=published,
            )
        )
    return papers


__all__ = ["ArxivClient", "ArxivPaperMeta"]
