"""arXiv Atom API client with timeout, rate limit, exponential backoff ()."""

from __future__ import annotations

import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field

logger = logging.getLogger("pipeline.crawler")

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


@dataclass
class PaperMeta:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    pdf_url: str
    abs_url: str
    published: str = ""
    updated: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FetchFailure:
    query: str
    error: str
    attempt: int
    at: float = field(default_factory=time.time)


class ArxivClient:
    """Respects arXiv courtesy: ~1 request / min_interval seconds + backoff on errors."""

    def __init__(
        self,
        *,
        timeout_s: float = 10.0,
        min_interval_s: float = 3.0,
        max_retries: int = 3,
        user_agent: str = "PaperMate-Crawler/0.1 (course prototype; contact: local)",
    ) -> None:
        self.timeout_s = timeout_s
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._last_request_at = 0.0
        self.failures: list[FetchFailure] = []

    def _throttle(self) -> None:
        gap = time.perf_counter() - self._last_request_at
        if gap < self.min_interval_s:
            sleep_for = self.min_interval_s - gap
            logger.info("rate_limit sleep_s=%.2f", sleep_for)
            time.sleep(sleep_for)

    def _http_get(self, url: str) -> bytes:
        self._throttle()
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        attempt = 0
        backoff = 1.0
        while True:
            attempt += 1
            try:
                self._last_request_at = time.perf_counter()
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.read()
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                self.failures.append(FetchFailure(query=url, error=str(exc), attempt=attempt))
                logger.warning("http_error attempt=%s/%s err=%s", attempt, self.max_retries, exc)
                if attempt >= self.max_retries:
                    raise
                time.sleep(backoff)
                backoff *= 2

    def search(
        self,
        *,
        keyword: str | None = None,
        search_query: str | None = None,
        start: int = 0,
        max_results: int = 50,
        sort_by: str = "relevance",
    ) -> list[PaperMeta]:
        q = search_query or f"all:{keyword}"
        params = urllib.parse.urlencode(
            {
                "search_query": q,
                "start": start,
                "max_results": max_results,
                "sortBy": sort_by,
                "sortOrder": "descending",
            }
        )
        url = f"{ARXIV_API}?{params}"
        xml_bytes = self._http_get(url)
        return _parse_feed(xml_bytes)


def _parse_feed(xml_bytes: bytes) -> list[PaperMeta]:
    root = ET.fromstring(xml_bytes)
    papers: list[PaperMeta] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        raw_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        arxiv_id = raw_id.rsplit("/abs/", 1)[-1]
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS) or ""
        abstract = entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or ""
        authors = [
            a.findtext("atom:name", default="", namespaces=ATOM_NS) or ""
            for a in entry.findall("atom:author", ATOM_NS)
        ]
        categories = [c.get("term", "") for c in entry.findall("atom:category", ATOM_NS)]
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS) or ""
        updated = entry.findtext("atom:updated", default="", namespaces=ATOM_NS) or ""
        base_id = re.sub(r"v\d+$", "", arxiv_id)
        papers.append(
            PaperMeta(
                arxiv_id=base_id,
                title=title,
                authors=[a for a in authors if a],
                abstract=abstract,
                categories=[c for c in categories if c],
                pdf_url=f"https://arxiv.org/pdf/{base_id}.pdf",
                abs_url=f"https://arxiv.org/abs/{base_id}",
                published=published,
                updated=updated,
            )
        )
    return papers
