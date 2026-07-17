""" · PDF download / extract / section heuristics / clean with page anchors."""

from __future__ import annotations

import logging
import re
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger("pipeline.parser")

_SECTION = re.compile(
    r"(?im)^\s*(\d+(?:\.\d+)*\.?\s+)?(abstract|introduction|related work|background|"
    r"method|methods|approach|architecture|experiment|experiments|results|"
    r"discussion|conclusion|references|acknowledg)\b.*"
)
_SPACE = re.compile(r"[ \t]+")


@dataclass
class Paragraph:
    para_id: str
    page: int
    section: str
    text: str


@dataclass
class ParseResult:
    arxiv_id: str
    ok: bool
    status: str  # parsed | parsed_degraded | parse_failed | fetch_failed
    pdf_path: str | None = None
    page_count: int = 0
    char_count: int = 0
    paragraphs: list[Paragraph] = field(default_factory=list)
    error: str | None = None
    elapsed_s: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def ensure_pdf(
    arxiv_id: str,
    pdf_dir: Path,
    *,
    pdf_url: str | None = None,
    search_dirs: list[Path] | None = None,
    timeout_s: float = 60.0,
) -> Path:
    """Reuse local PDF if present; otherwise download from arXiv."""
    pdf_dir.mkdir(parents=True, exist_ok=True)
    # exact / versioned names
    candidates = list(pdf_dir.glob(f"{arxiv_id}*.pdf"))
    if search_dirs:
        for d in search_dirs:
            if d.exists():
                candidates.extend(d.glob(f"{arxiv_id}*.pdf"))
    if candidates:
        # prefer already in pdf_dir
        local = [c for c in candidates if c.parent == pdf_dir]
        src = local[0] if local else candidates[0]
        dest = pdf_dir / src.name
        if src.resolve() != dest.resolve():
            dest.write_bytes(src.read_bytes())
        return dest

    url = pdf_url or f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    dest = pdf_dir / f"{arxiv_id}.pdf"
    logger.info("download_pdf id=%s url=%s", arxiv_id, url)
    req = urllib.request.Request(url, headers={"User-Agent": "PaperMate-Parser/0.1"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF")
    dest.write_bytes(data)
    return dest


def clean_line(text: str) -> str:
    text = text.replace("\x00", "")
    text = _SPACE.sub(" ", text)
    return text.strip()


def extract_paragraphs(pdf_path: Path, *, max_pages: int | None = None) -> tuple[list[Paragraph], int]:
    reader = PdfReader(str(pdf_path))
    n_pages = len(reader.pages)
    pages = reader.pages[: max_pages or n_pages]
    paras: list[Paragraph] = []
    section = "body"
    pid = 0
    for page_idx, page in enumerate(pages, start=1):
        raw = page.extract_text() or ""
        for block in re.split(r"\n\s*\n", raw):
            lines = [clean_line(x) for x in block.splitlines()]
            lines = [x for x in lines if x]
            if not lines:
                continue
            head = lines[0]
            if _SECTION.match(head) and len(head) < 80:
                section = re.sub(r"^\d+(\.\d+)*\.?\s*", "", head, flags=re.I).lower()[:64]
                body = clean_line(" ".join(lines[1:]))
            else:
                body = clean_line(" ".join(lines))
            if len(body) < 40:
                continue
            paras.append(
                Paragraph(
                    para_id=f"p{page_idx}_{pid}",
                    page=page_idx,
                    section=section,
                    text=body[:2000],
                )
            )
            pid += 1
    return paras, n_pages


def parse_pdf_file(
    arxiv_id: str,
    pdf_path: Path,
    *,
    max_pages: int | None = None,
    min_chars: int = 500,
) -> ParseResult:
    import time

    t0 = time.perf_counter()
    try:
        paragraphs, page_count = extract_paragraphs(pdf_path, max_pages=max_pages)
        chars = sum(len(p.text) for p in paragraphs)
        elapsed = round(time.perf_counter() - t0, 3)
        if chars < min_chars:
            return ParseResult(
                arxiv_id=arxiv_id,
                ok=False,
                status="parse_failed",
                pdf_path=str(pdf_path),
                page_count=page_count,
                char_count=chars,
                paragraphs=paragraphs,
                error=f"insufficient text ({chars} chars)",
                elapsed_s=elapsed,
            )
        degraded = bool(max_pages and page_count > max_pages)
        status = "parsed_degraded" if degraded else "parsed"
        return ParseResult(
            arxiv_id=arxiv_id,
            ok=True,
            status=status,
            pdf_path=str(pdf_path),
            page_count=page_count,
            char_count=chars,
            paragraphs=paragraphs,
            elapsed_s=elapsed,
        )
    except Exception as exc:  # noqa: BLE001
        return ParseResult(
            arxiv_id=arxiv_id,
            ok=False,
            status="parse_failed",
            pdf_path=str(pdf_path),
            error=str(exc),
            elapsed_s=round(time.perf_counter() - t0, 3),
        )
