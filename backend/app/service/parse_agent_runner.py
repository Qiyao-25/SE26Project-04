"""Background parse runner: fetch text → Summarize Agent → persist Wiki + chunks."""

from __future__ import annotations

import logging
import re
import tempfile
import urllib.request
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.agents.deepseek_client import DeepSeekError
from app.agents.summarize_agent import SummarizeAgent
from app.core.config import Settings, get_settings
from app.model import ParseTask, Paper
from app.schema.papers import ParseResultCommit, StructuredResultInput, TextChunkInput
from app.service.tasks import save_parse_result

logger = logging.getLogger("papermate.parse_agent")


def run_parse_agent_job(engine, task_id: int, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        _execute(session, task_id, settings)
    except Exception:  # noqa: BLE001
        logger.exception("parse_agent_job_crashed task_id=%s", task_id)
        try:
            session.rollback()
            _fail(session, task_id, "WORKER_ERROR")
        except Exception:  # noqa: BLE001
            logger.exception("parse_agent_fail_writeback_failed task_id=%s", task_id)
    finally:
        session.close()


def _execute(session: Session, task_id: int, settings: Settings) -> None:
    task = session.get(ParseTask, task_id)
    if task is None or task.status not in {"queued", "running"}:
        logger.info("parse_agent_skip task_id=%s status=%s", task_id, getattr(task, "status", None))
        return

    paper = session.get(Paper, task.paper_id)
    if paper is None:
        _fail(session, task_id, "PAPER_NOT_FOUND")
        return

    if not settings.parse_agent_ready:
        _fail(session, task_id, "AGENT_NOT_CONFIGURED")
        return

    _mark_running(session, task, paper, stage="fetch")
    body_text, page_count, source = _extract_paper_text(paper, settings)
    if not body_text.strip() and not (paper.abstract or "").strip():
        _fail(session, task_id, "PARSE_FAILED")
        return

    _mark_running(session, task, paper, stage="summarize")
    try:
        wiki = SummarizeAgent(settings).run(
            title=paper.title or "",
            abstract=paper.abstract or "",
            body_text=body_text or paper.abstract or "",
            arxiv_id=paper.arxiv_id or str(paper.id),
        )
    except DeepSeekError as exc:
        logger.error("summarize_agent_failed task_id=%s err=%s", task_id, exc)
        _fail(session, task_id, "STRUCTURED_RESULT_FAILED")
        return

    _mark_running(session, task, paper, stage="persist")
    chunks = _text_to_chunks(body_text or paper.abstract or "", max_chunks=80)
    results = [
        StructuredResultInput(
            result_type=row["result_type"],
            version=int(row.get("version") or 1),
            content_json=row["content_json"],
            source_locator={**(row.get("source_locator") or {}), "extract_source": source},
            confidence=row.get("confidence"),
        )
        for row in wiki.to_structured_rows(page_count=page_count)
    ]
    chunk_inputs = [
        TextChunkInput(
            chunk_id=item["chunk_id"],
            page_no=item.get("page_no"),
            section=item.get("section"),
            content=item["content"],
        )
        for item in chunks
    ]
    if not chunk_inputs:
        chunk_inputs = [
            TextChunkInput(
                chunk_id=f"{paper.arxiv_id or paper.id}-abstract",
                page_no=1,
                section="abstract",
                content=(paper.abstract or wiki.summary)[:2000],
            )
        ]

    save_parse_result(
        session,
        task_id,
        ParseResultCommit(chunks=chunk_inputs, results=results),
    )
    logger.info(
        "parse_agent_succeeded task_id=%s paper_id=%s chunks=%s source=%s",
        task_id,
        paper.id,
        len(chunk_inputs),
        source,
    )


def _mark_running(session: Session, task: ParseTask, paper: Paper, *, stage: str) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    task.status = "running"
    task.stage = stage
    task.started_at = task.started_at or now
    task.error_code = None
    paper.ingest_status = "parsing"
    session.commit()


def _fail(session: Session, task_id: int, error_code: str) -> None:
    from datetime import datetime, timezone

    task = session.get(ParseTask, task_id)
    if task is None:
        return
    task.status = "failed"
    task.stage = "failed"
    task.error_code = error_code[:64]
    task.finished_at = datetime.now(timezone.utc)
    paper = session.get(Paper, task.paper_id)
    if paper is not None:
        paper.ingest_status = "failed"
    session.commit()


def _extract_paper_text(paper: Paper, settings: Settings) -> tuple[str, int, str]:
    pdf_url = (paper.pdf_url or "").strip()
    if not pdf_url and paper.arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{paper.arxiv_id}.pdf"

    if pdf_url:
        try:
            text, pages = _download_and_extract_pdf(pdf_url, max_pages=settings.parse_agent_max_pages)
            if text.strip():
                return text, pages, "pdf"
        except Exception as exc:  # noqa: BLE001
            logger.warning("pdf_extract_failed arxiv_id=%s err=%s", paper.arxiv_id, exc)

    abstract = (paper.abstract or "").strip()
    return abstract, 0, "abstract_fallback"


def _download_and_extract_pdf(url: str, *, max_pages: int) -> tuple[str, int]:
    request = urllib.request.Request(url, headers={"User-Agent": "PaperMate-ParseAgent/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        pdf_bytes = response.read()

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("未安装 pypdf，无法解析 PDF") from exc

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        reader = PdfReader(str(tmp_path))
        pages = min(len(reader.pages), max_pages)
        parts: list[str] = []
        for index in range(pages):
            try:
                text = reader.pages[index].extract_text() or ""
            except Exception:  # noqa: BLE001
                text = ""
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                parts.append(f"[page {index + 1}] {text}")
        return "\n\n".join(parts), pages
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _text_to_chunks(text: str, *, max_chunks: int = 80) -> list[dict]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []

    # Prefer page markers from PDF extract
    page_blocks = re.split(r"\[page\s+(\d+)\]\s*", cleaned)
    chunks: list[dict] = []
    if len(page_blocks) > 1:
        # split => ['', '1', 'text', '2', 'text', ...]
        it = iter(page_blocks[1:])
        for page_no, body in zip(it, it):
            for piece in _split_pieces(body, size=700):
                if len(chunks) >= max_chunks:
                    return chunks
                chunks.append(
                    {
                        "chunk_id": f"p{page_no}-{len(chunks) + 1}",
                        "page_no": int(page_no),
                        "section": "body",
                        "content": piece,
                    }
                )
        return chunks

    for piece in _split_pieces(cleaned, size=700):
        if len(chunks) >= max_chunks:
            break
        chunks.append(
            {
                "chunk_id": f"c-{len(chunks) + 1}",
                "page_no": 1,
                "section": "body",
                "content": piece,
            }
        )
    return chunks


def _split_pieces(text: str, *, size: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [text[i : i + size].strip() for i in range(0, len(text), size) if text[i : i + size].strip()]


__all__ = ["run_parse_agent_job"]
