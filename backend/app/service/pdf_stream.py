"""Stream paper PDF bytes for in-browser viewers (same-origin, selectable text)."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from pathlib import Path

from fastapi.responses import Response
from sqlalchemy.orm import Session

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


def load_paper_pdf_bytes(session: Session, paper_id: int, *, timeout_s: float = 60.0) -> tuple[bytes, str]:
    paper = session.get(Paper, paper_id)
    if paper is None or paper.deleted_at is not None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)

    content = session.get(PaperContent, paper_id)
    if content and content.storage_path:
        path = Path(content.storage_path)
        if path.is_file():
            data = path.read_bytes()
            if data[:4] == b"%PDF" or data[:5] == b"%PDF-":
                return data, "application/pdf"

    pdf_url = _resolve_pdf_url(paper)
    if not pdf_url:
        raise PaperServiceError("PDF_NOT_FOUND", "当前论文没有可读取的 PDF", 404)

    req = urllib.request.Request(
        pdf_url,
        headers={
            "User-Agent": "PaperMate/0.1 (academic reader; +https://github.com/Qiyao-25/SE26Project-04)",
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
    if not data:
        raise PaperServiceError("PDF_EMPTY", "PDF 内容为空", 502)
    return data, content_type or "application/pdf"


def pdf_response(data: bytes, *, filename: str = "paper.pdf") -> Response:
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=data, media_type="application/pdf", headers=headers)
