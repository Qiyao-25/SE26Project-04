"""PDF-first document parsing with HTML/ar5iv fallback."""

from __future__ import annotations

from pathlib import Path

from .html_parse import ensure_html, parse_html_file
from .pdf_parse import ParseResult, ensure_pdf, parse_pdf_file


def parse_document(
    arxiv_id: str,
    pdf_dir: Path,
    html_dir: Path,
    *,
    pdf_url: str | None = None,
    html_url: str | None = None,
    pdf_search_dirs: list[Path] | None = None,
    html_search_dirs: list[Path] | None = None,
    max_pages: int | None = None,
    min_chars: int = 500,
    prefer_html: bool = False,
) -> ParseResult:
    attempts = ("html", "pdf") if prefer_html else ("pdf", "html")
    errors: list[str] = []
    for source in attempts:
        try:
            if source == "pdf":
                path = ensure_pdf(arxiv_id, pdf_dir, pdf_url=pdf_url, search_dirs=pdf_search_dirs, timeout_s=60)
                result = parse_pdf_file(arxiv_id, path, max_pages=max_pages, min_chars=min_chars)
            else:
                path = ensure_html(arxiv_id, html_dir, html_url=html_url, search_dirs=html_search_dirs, timeout_s=60)
                result = parse_html_file(arxiv_id, path, min_chars=min_chars)
            if result.ok:
                return result
            errors.append(f"{source}: {result.error or result.status}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}: {exc}")
    return ParseResult(arxiv_id, False, "parse_failed", error="; ".join(errors))


__all__ = ["parse_document"]
