"""Same-origin PDF assets for in-browser viewers (alphaXiv-style cache + stream)."""

from __future__ import annotations

import hashlib
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path

from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.model import Paper, PaperContent
from app.service.papers import PaperServiceError

logger = logging.getLogger("papermate.pdf_stream")

MAX_PDF_BYTES = 40 * 1024 * 1024


def _resolve_pdf_url(paper: Paper) -> str | None:
    url = (paper.pdf_url or "").strip()
    if url:
        return url
    if paper.arxiv_id:
        return f"https://arxiv.org/pdf/{paper.arxiv_id}.pdf"
    return None


def _storage_dir(settings: Settings) -> Path:
    path = Path(settings.paper_storage_dir or "data/pdfs")
    if not path.is_absolute():
        # Resolve relative to backend package root (…/backend)
        backend_root = Path(__file__).resolve().parents[2]
        path = backend_root / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path_for(paper: Paper, settings: Settings) -> Path:
    raw = paper.arxiv_id or f"paper-{paper.id}"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(raw))
    return _storage_dir(settings) / f"{safe}.pdf"


def _is_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF" or data[:5] == b"%PDF-"


def _persist_cache(session: Session, paper: Paper, path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    checksum = hashlib.sha256(data).hexdigest()
    row = session.get(PaperContent, paper.id)
    if row is None:
        row = PaperContent(
            paper_id=paper.id,
            storage_path=str(path),
            checksum=checksum,
            mime_type="application/pdf",
        )
        session.add(row)
    else:
        row.storage_path = str(path)
        row.checksum = checksum
        row.mime_type = "application/pdf"
    try:
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("pdf_cache_meta_failed paper_id=%s", paper.id)


def load_paper_pdf_bytes(
    session: Session,
    paper_id: int,
    *,
    timeout_s: float = 60.0,
    settings: Settings | None = None,
) -> tuple[bytes, str]:
    """Return PDF bytes: local PaperContent / disk cache first, else fetch and cache."""
    settings = settings or get_settings()
    paper = session.get(Paper, paper_id)
    if paper is None or paper.deleted_at is not None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)

    content = session.get(PaperContent, paper_id)
    if content and content.storage_path:
        path = Path(content.storage_path)
        if path.is_file():
            data = path.read_bytes()
            if _is_pdf(data):
                return data, "application/pdf"

    cache_path = _cache_path_for(paper, settings)
    if cache_path.is_file():
        data = cache_path.read_bytes()
        if _is_pdf(data):
            _persist_cache(session, paper, cache_path, data)
            return data, "application/pdf"

    pdf_url = _resolve_pdf_url(paper)
    if not pdf_url:
        raise PaperServiceError("PDF_NOT_FOUND", "当前论文没有可读取的 PDF", 404)

    req = urllib.request.Request(
        pdf_url,
        headers={
            "User-Agent": "PaperMate/0.2 (academic reader; course demo)",
            "Accept": "application/pdf,*/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read(MAX_PDF_BYTES + 1)
            content_type = (resp.headers.get("Content-Type") or "application/pdf").split(";")[0].strip()
    except urllib.error.HTTPError as exc:
        logger.warning("pdf_proxy_http paper_id=%s status=%s", paper_id, exc.code)
        raise PaperServiceError("PDF_FETCH_FAILED", f"拉取 PDF 失败（HTTP {exc.code}）", 502) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf_proxy_failed paper_id=%s err=%s", paper_id, exc)
        raise PaperServiceError("PDF_FETCH_FAILED", f"拉取 PDF 失败：{exc}", 502) from exc

    if len(data) > MAX_PDF_BYTES:
        raise PaperServiceError("PDF_TOO_LARGE", "PDF 过大，无法在线预览", 413)
    if not data or not _is_pdf(data):
        raise PaperServiceError("PDF_EMPTY", "PDF 内容无效或为空", 502)

    try:
        _persist_cache(session, paper, cache_path, data)
    except Exception:  # noqa: BLE001
        logger.exception("pdf_cache_write_failed paper_id=%s path=%s", paper_id, cache_path)

    return data, content_type or "application/pdf"


def pdf_response(data: bytes, *, filename: str = "paper.pdf") -> Response:
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Cache-Control": "private, max-age=600",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=data, media_type="application/pdf", headers=headers)
