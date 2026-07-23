"""Minimal arXiv Atom API + RSS client for subscription sync / scheduled crawl."""

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

DEFAULT_ARXIV_API = "https://export.arxiv.org/api/query"
DEFAULT_ARXIV_RSS_BASE = "https://rss.arxiv.org/rss"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
# RSS 2.0 has no default namespace; some feeds use atom too.


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
    def __init__(
        self,
        *,
        api_base: str = DEFAULT_ARXIV_API,
        rss_base: str = DEFAULT_ARXIV_RSS_BASE,
        timeout_s: float = 60.0,
        min_interval_s: float = 3.0,
        max_retries: int = 4,
        rate_limit_wait_s: float = 45.0,
    ) -> None:
        self.api_base = (api_base or DEFAULT_ARXIV_API).rstrip("?")
        self.rss_base = (rss_base or DEFAULT_ARXIV_RSS_BASE).rstrip("/")
        self.timeout_s = timeout_s
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.rate_limit_wait_s = rate_limit_wait_s
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        gap = time.perf_counter() - self._last_request_at
        if gap < self.min_interval_s:
            time.sleep(self.min_interval_s - gap)

    def _http_get(self, url: str) -> bytes:
        self._throttle()
        req = urllib.request.Request(url, headers={"User-Agent": "PaperMate-Backend/0.2 (course demo; mailto:course@local)"})
        attempt = 0
        backoff = 2.0
        while True:
            attempt += 1
            try:
                self._last_request_at = time.perf_counter()
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")[:200]
                except Exception:  # noqa: BLE001
                    pass
                logger.warning(
                    "arxiv_http_status attempt=%s/%s code=%s body=%s",
                    attempt,
                    self.max_retries,
                    exc.code,
                    body,
                )
                if exc.code == 429 and attempt < self.max_retries:
                    wait = self.rate_limit_wait_s * attempt
                    logger.info("arxiv_rate_limited waiting_s=%s", wait)
                    time.sleep(wait)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                logger.warning("arxiv_http_error attempt=%s/%s err=%s", attempt, self.max_retries, exc)
                if attempt >= self.max_retries:
                    raise
                time.sleep(backoff)
                backoff *= 2

    def search(
        self,
        *,
        search_query: str,
        max_results: int = 5,
        start: int = 0,
        sort_by: str = "submittedDate",
    ) -> list[ArxivPaperMeta]:
        params = urllib.parse.urlencode(
            {
                "search_query": search_query,
                "start": max(0, int(start)),
                "max_results": max_results,
                "sortBy": sort_by,
                "sortOrder": "descending",
            }
        )
        return _parse_atom_feed(self._http_get(f"{self.api_base}?{params}"))[:max_results]

    def fetch_category_rss(self, category: str, *, max_results: int = 5) -> list[ArxivPaperMeta]:
        """Prefer RSS for category sync — often reachable when API is 429-throttled."""
        cat = category.strip()
        if not cat:
            return []
        url = f"{self.rss_base}/{urllib.parse.quote(cat)}"
        raw = self._http_get(url)
        papers = _parse_rss_or_atom(raw)
        for paper in papers:
            if cat and cat not in paper.categories:
                paper.categories = [cat, *paper.categories]
        return papers[:max_results]

    def fetch_by_id(self, arxiv_id: str) -> ArxivPaperMeta | None:
        aid = _arxiv_id_from_text(arxiv_id)
        if not aid:
            return None
        params = urllib.parse.urlencode({"id_list": aid})
        papers = _parse_atom_feed(self._http_get(f"{self.api_base}?{params}"))
        return papers[0] if papers else None

    def fetch_by_title(self, title: str, *, max_results: int = 5) -> list[ArxivPaperMeta]:
        cleaned = " ".join((title or "").replace('"', " ").split()).strip()
        if not cleaned:
            return []
        # Prefer exact-ish title phrase; fall back to all-fields search.
        try:
            hits = self.search(
                search_query=f'ti:"{cleaned}"',
                max_results=max_results,
                sort_by="relevance",
            )
        except Exception:  # noqa: BLE001
            hits = []
        if hits:
            return hits
        return self.search(
            search_query=f'all:"{cleaned}"',
            max_results=max_results,
            sort_by="relevance",
        )

    def resolve_query(self, query: str, *, max_results: int = 5) -> list[ArxivPaperMeta]:
        """Resolve an arXiv id, abs/pdf URL, or title into paper metadata."""
        text = (query or "").strip()
        if not text:
            return []
        id_match = re.search(
            r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?",
            text,
            flags=re.I,
        )
        if id_match or re.fullmatch(r"[\w\-]+/\d{7}", text):
            paper = self.fetch_by_id(text)
            return [paper] if paper else []
        return self.fetch_by_title(text, max_results=max_results)


def _arxiv_id_from_text(value: str) -> str:
    text = (value or "").strip()
    if "/abs/" in text:
        text = text.rsplit("/abs/", 1)[-1]
    if "/pdf/" in text:
        text = text.rsplit("/pdf/", 1)[-1]
    text = text.replace(".pdf", "")
    # RSS / OAI identifiers: oai:arXiv.org:2401.01234
    if "arXiv.org:" in text:
        text = text.rsplit("arXiv.org:", 1)[-1]
    elif text.lower().startswith("oai:"):
        text = text.rsplit(":", 1)[-1]
    return re.sub(r"v\d+$", "", text.strip())


def _split_author_names(raw_authors: list[str]) -> list[str]:
    """RSS often packs every author into one dc:creator string."""
    names: list[str] = []
    for raw in raw_authors or []:
        text = " ".join(str(raw or "").split()).strip()
        if not text:
            continue
        # Multi-author blob: "Alice, Bob, Carol"
        if "," in text and len(text) > 80:
            parts = [part.strip() for part in text.split(",")]
        elif " and " in text.casefold() and len(text) > 80:
            parts = [part.strip() for part in re.split(r"\s+and\s+", text, flags=re.I)]
        else:
            parts = [text]
        for part in parts:
            name = part.strip(" ;")
            if not name:
                continue
            if len(name) > 255:
                name = name[:255].rstrip()
            if name and name not in names:
                names.append(name)
    return names[:40]


def _parse_atom_feed(xml_bytes: bytes) -> list[ArxivPaperMeta]:
    root = ET.fromstring(xml_bytes)
    papers: list[ArxivPaperMeta] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        raw_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        arxiv_id = _arxiv_id_from_text(raw_id)
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").split())
        abstract = " ".join((entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").split())
        authors = [
            a.findtext("atom:name", default="", namespaces=ATOM_NS) or ""
            for a in entry.findall("atom:author", ATOM_NS)
        ]
        categories = [c.get("term", "") for c in entry.findall("atom:category", ATOM_NS)]
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS) or ""
        if not arxiv_id:
            continue
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


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _parse_rss_or_atom(xml_bytes: bytes) -> list[ArxivPaperMeta]:
    """Parse arXiv RSS 2.0 (common on rss.arxiv.org) or Atom."""
    root = ET.fromstring(xml_bytes)
    root_name = _local(root.tag).lower()
    if root_name == "feed" or root.findall("atom:entry", ATOM_NS):
        return _parse_atom_feed(xml_bytes)

    channel = root.find("channel")
    if channel is None:
        # namespaced channel
        for child in list(root):
            if _local(child.tag).lower() == "channel":
                channel = child
                break
    if channel is None:
        return _parse_atom_feed(xml_bytes)

    papers: list[ArxivPaperMeta] = []
    for item in list(channel):
        if _local(item.tag).lower() != "item":
            continue
        title = ""
        link = ""
        description = ""
        guid = ""
        pub_date = ""
        creators: list[str] = []
        categories: list[str] = []
        for child in list(item):
            name = _local(child.tag).lower()
            text = (child.text or "").strip()
            if name == "title":
                title = " ".join(text.split())
            elif name == "link":
                link = text
            elif name in {"description", "summary"}:
                description = " ".join(text.split())
            elif name == "guid":
                guid = text
            elif name in {"pubdate", "published", "updated"}:
                pub_date = text
            elif name in {"creator", "author"}:
                if text:
                    creators.append(text)
            elif name == "category" and text:
                categories.append(text)
        arxiv_id = _arxiv_id_from_text(guid or link)
        if not arxiv_id:
            continue
        papers.append(
            ArxivPaperMeta(
                arxiv_id=arxiv_id,
                title=title or arxiv_id,
                authors=_split_author_names(creators),
                abstract=description,
                categories=categories,
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                abs_url=f"https://arxiv.org/abs/{arxiv_id}",
                published=pub_date,
            )
        )
    return papers


__all__ = ["ArxivClient", "ArxivPaperMeta"]
