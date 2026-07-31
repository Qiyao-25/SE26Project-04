"""Same-origin PDF cache + stream (alphaXiv-style storage; annotation UI comes later)."""

from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.model import Paper, PaperContent
from app.service.papers import PaperServiceError

logger = logging.getLogger("papermate.pdf_stream")

MAX_PDF_BYTES = 40 * 1024 * 1024


def normalize_arxiv_id(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.lower().startswith("oai:arxiv.org:"):
        raw = raw.split(":", 2)[-1]
    raw = raw.removeprefix("arXiv:").removeprefix("arxiv:")
    raw = raw.strip().removesuffix(".pdf")
    return raw or None


def _resolve_pdf_url(paper: Paper) -> str | None:
    url = (paper.pdf_url or "").strip()
    if url and "oai:arXiv.org:" not in url and "/pdf/oai:" not in url:
        return url
    arxiv_id = normalize_arxiv_id(paper.arxiv_id)
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    if url:
        fixed = normalize_arxiv_id(url.rsplit("/", 1)[-1])
        if fixed:
            return f"https://arxiv.org/pdf/{fixed}.pdf"
    return None


def resolve_storage_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    path = Path(settings.paper_storage_dir or "data/pdfs")
    if not path.is_absolute():
        backend_root = Path(__file__).resolve().parents[2]
        path = backend_root / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path_for(paper: Paper, settings: Settings) -> Path:
    raw = normalize_arxiv_id(paper.arxiv_id) or f"paper-{paper.id}"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(raw))
    return resolve_storage_dir(settings) / f"{safe}.pdf"


def _is_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF"


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


def local_pdf_path(session: Session, paper: Paper, settings: Settings) -> Path | None:
    content = session.get(PaperContent, paper.id)
    if content and content.storage_path:
        path = Path(content.storage_path)
        if path.is_file():
            return path
    cache_path = _cache_path_for(paper, settings)
    if cache_path.is_file():
        return cache_path
    return None


def ensure_paper_pdf_cached(
    session: Session,
    paper_id: int,
    *,
    timeout_s: float = 60.0,
    settings: Settings | None = None,
    force: bool = False,
) -> Path:
    """Download PDF if missing and return the local path."""
    settings = settings or get_settings()
    paper = session.get(Paper, paper_id)
    if paper is None or paper.deleted_at is not None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)

    if not force:
        existing = local_pdf_path(session, paper, settings)
        if existing is not None:
            data = existing.read_bytes()
            if _is_pdf(data):
                content = session.get(PaperContent, paper.id)
                if content is None or Path(content.storage_path) != existing:
                    _persist_cache(session, paper, existing, data)
                return existing

    pdf_url = _resolve_pdf_url(paper)
    if not pdf_url:
        raise PaperServiceError("PDF_NOT_FOUND", "当前论文没有可读取的 PDF", 404)

    cache_path = _cache_path_for(paper, settings)
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
    except urllib.error.HTTPError as exc:
        logger.warning("pdf_proxy_http paper_id=%s status=%s", paper_id, exc.code)
        raise PaperServiceError("PDF_FETCH_FAILED", f"拉取 PDF 失败（HTTP {exc.code}）", 502) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf_proxy_failed paper_id=%s err=%s", paper_id, exc)
        raise PaperServiceError("PDF_FETCH_FAILED", f"拉取 PDF 失败：{exc}", 502) from exc

    if len(data) > MAX_PDF_BYTES:
        raise PaperServiceError("PDF_TOO_LARGE", "PDF 过大，无法缓存", 413)
    if not data or not _is_pdf(data):
        raise PaperServiceError("PDF_EMPTY", "PDF 内容无效或为空", 502)

    _persist_cache(session, paper, cache_path, data)
    return cache_path


def load_paper_pdf_bytes(
    session: Session,
    paper_id: int,
    *,
    timeout_s: float = 60.0,
    settings: Settings | None = None,
) -> tuple[bytes, str]:
    path = ensure_paper_pdf_cached(session, paper_id, timeout_s=timeout_s, settings=settings)
    return path.read_bytes(), "application/pdf"


def list_papers_missing_pdf(session: Session, *, limit: int = 100) -> list[Paper]:
    """Papers without a readable local PDF file (for backfill)."""
    settings = get_settings()
    rows = session.scalars(
        select(Paper)
        .where(Paper.deleted_at.is_(None))
        .order_by(Paper.id.asc())
        .limit(max(limit * 3, limit))
    ).all()
    missing: list[Paper] = []
    for paper in rows:
        if local_pdf_path(session, paper, settings) is None:
            missing.append(paper)
        if len(missing) >= limit:
            break
    return missing



def cache_paper_ids(
    session: Session,
    paper_ids: list[int],
    *,
    settings: Settings | None = None,
    delay_s: float = 0.25,
) -> dict:
    """Best-effort PDF cache for newly ingested paper IDs (crawl / fetch-one)."""
    settings = settings or get_settings()
    ok: list[int] = []
    failed: list[dict] = []
    unique_ids = list(dict.fromkeys(int(pid) for pid in paper_ids if pid is not None))
    for index, paper_id in enumerate(unique_ids):
        try:
            ensure_paper_pdf_cached(session, paper_id, settings=settings)
            ok.append(paper_id)
        except PaperServiceError as exc:
            failed.append({"paper_id": paper_id, "error": exc.code, "message": exc.message})
            logger.warning("pdf_ingest_cache_fail paper_id=%s code=%s", paper_id, exc.code)
        except Exception as exc:  # noqa: BLE001
            failed.append({"paper_id": paper_id, "error": "UNEXPECTED", "message": str(exc)})
            logger.exception("pdf_ingest_cache_unexpected paper_id=%s", paper_id)
        if delay_s > 0 and index + 1 < len(unique_ids):
            time.sleep(delay_s)
    return {"requested": len(unique_ids), "succeeded": len(ok), "failed": len(failed), "paper_ids": ok, "errors": failed[:30]}


def sync_missing_paper_pdfs(
    session: Session,
    *,
    limit: int = 50,
    delay_s: float = 0.4,
    settings: Settings | None = None,
) -> dict:
    """Backfill local PDF cache for already-ingested papers."""
    settings = settings or get_settings()
    targets = list_papers_missing_pdf(session, limit=limit)
    ok: list[int] = []
    failed: list[dict] = []
    skipped = 0

    for index, paper in enumerate(targets):
        if not _resolve_pdf_url(paper):
            skipped += 1
            failed.append({"paper_id": paper.id, "arxiv_id": paper.arxiv_id, "error": "PDF_NOT_FOUND"})
            continue
        try:
            ensure_paper_pdf_cached(session, paper.id, settings=settings)
            ok.append(paper.id)
            logger.info("pdf_sync_ok paper_id=%s arxiv_id=%s", paper.id, paper.arxiv_id)
        except PaperServiceError as exc:
            failed.append({"paper_id": paper.id, "arxiv_id": paper.arxiv_id, "error": exc.code, "message": exc.message})
            logger.warning("pdf_sync_fail paper_id=%s code=%s", paper.id, exc.code)
        except Exception as exc:  # noqa: BLE001
            failed.append({"paper_id": paper.id, "arxiv_id": paper.arxiv_id, "error": "UNEXPECTED", "message": str(exc)})
            logger.exception("pdf_sync_unexpected paper_id=%s", paper.id)
        if delay_s > 0 and index + 1 < len(targets):
            time.sleep(delay_s)

    return {
        "requested": len(targets),
        "succeeded": len(ok),
        "failed": len(failed),
        "skipped": skipped,
        "paper_ids": ok,
        "errors": failed[:50],
        "storage_dir": str(resolve_storage_dir(settings)),
    }


def pdf_cache_stats(session: Session, settings: Settings | None = None) -> dict:
    from sqlalchemy import func

    settings = settings or get_settings()
    total_papers = session.scalar(select(func.count()).select_from(Paper).where(Paper.deleted_at.is_(None))) or 0
    content_rows = session.scalar(select(func.count()).select_from(PaperContent)) or 0
    storage = resolve_storage_dir(settings)
    files = list(storage.glob("*.pdf")) if storage.is_dir() else []
    return {
        "papers": int(total_papers),
        "paper_content_rows": int(content_rows),
        "disk_pdf_files": len(files),
        "storage_dir": str(storage),
    }


def pdf_response(data: bytes, *, filename: str = "paper.pdf") -> Response:
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Cache-Control": "private, max-age=600",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=data, media_type="application/pdf", headers=headers)
