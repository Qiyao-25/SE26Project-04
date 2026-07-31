"""HTML/ar5iv download and paragraph extraction with section anchors."""

from __future__ import annotations

import logging
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from .pdf_parse import ParseResult, Paragraph, clean_line

logger = logging.getLogger("pipeline.parser.html")

_BLOCK_TAGS = {"article", "div", "li", "p", "section", "td", "th"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {"script", "style", "svg", "noscript"}


class _ArxivHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.section = "body"
        self._skip_depth = 0
        self._buffer: list[str] = []
        self._paragraphs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _HEADING_TAGS:
            self._flush()
            self._buffer.append("\n")
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in _HEADING_TAGS:
            text = clean_line(" ".join(self._buffer))
            self._buffer.clear()
            if text:
                self.section = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", text).lower()[:64] or "body"
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self._buffer.append(data)

    def _flush(self) -> None:
        text = clean_line(" ".join(self._buffer))
        self._buffer.clear()
        if len(text) >= 40:
            self._paragraphs.append((self.section, text[:2000]))

    def paragraphs(self) -> list[Paragraph]:
        self._flush()
        return [Paragraph(f"h1_{index}", 1, section, text) for index, (section, text) in enumerate(self._paragraphs)]


def ensure_html(
    arxiv_id: str,
    html_dir: Path,
    *,
    html_url: str | None = None,
    search_dirs: list[Path] | None = None,
    timeout_s: float = 60.0,
) -> Path:
    """Reuse local HTML or download the ar5iv rendering."""
    html_dir.mkdir(parents=True, exist_ok=True)
    candidates = list(html_dir.glob(f"{arxiv_id}*.html"))
    for directory in search_dirs or []:
        if directory.exists():
            candidates.extend(directory.glob(f"{arxiv_id}*.html"))
    if candidates:
        source = next((item for item in candidates if item.parent == html_dir), candidates[0])
        target = html_dir / source.name
        if source.resolve() != target.resolve():
            target.write_bytes(source.read_bytes())
        return target

    url = html_url or f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
    target = html_dir / f"{arxiv_id}.html"
    logger.info("download_html id=%s url=%s", arxiv_id, url)
    request = urllib.request.Request(url, headers={"User-Agent": "PaperMate-Parser/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        data = response.read()
    if b"<html" not in data.lower() and b"<!doctype" not in data.lower():
        raise ValueError("not HTML")
    target.write_bytes(data)
    return target


def parse_html_file(arxiv_id: str, html_path: Path, *, min_chars: int = 500) -> ParseResult:
    import time

    started = time.perf_counter()
    try:
        parser = _ArxivHtmlParser()
        parser.feed(html_path.read_text(encoding="utf-8", errors="replace"))
        paragraphs = parser.paragraphs()
        chars = sum(len(item.text) for item in paragraphs)
        elapsed = round(time.perf_counter() - started, 3)
        if chars < min_chars:
            return ParseResult(arxiv_id, False, "parse_failed", str(html_path), 1, chars, paragraphs, f"insufficient HTML text ({chars} chars)", elapsed, "html")
        return ParseResult(arxiv_id, True, "parsed", str(html_path), 1, chars, paragraphs, None, elapsed, "html")
    except Exception as exc:  # noqa: BLE001
        return ParseResult(arxiv_id, False, "parse_failed", str(html_path), 0, 0, [], str(exc), round(time.perf_counter() - started, 3), "html")


__all__ = ["ensure_html", "parse_html_file"]
