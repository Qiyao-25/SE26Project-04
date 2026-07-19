"""Background parse runner: fetch text → Summarize Agent → persist Wiki + chunks."""

from __future__ import annotations

import logging
import re
import tempfile
import urllib.request
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.agents.llm_client import LlmError
from app.agents.summarize_agent import SummarizeAgent, build_fallback_summary
from app.agents.graph_agent import GraphAgent
from app.core.config import Settings, get_settings
from app.model import ParseTask, Paper
from app.schema.papers import ParseResultCommit, StructuredResultInput, TextChunkInput
from app.service.papers import get_related_paper_payloads
from app.service.tasks import save_parse_result
from app.repository.papers import list_papers

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

    _mark_running(session, task, paper, stage="fetch")
    body_text, page_count, source = _extract_paper_text(paper, settings)
    if not body_text.strip() and not (paper.abstract or "").strip():
        _fail(session, task_id, "PARSE_FAILED")
        return

    _mark_running(session, task, paper, stage="summarize")
    if settings.parse_agent_ready:
        try:
            wiki = SummarizeAgent(settings).run(
                title=paper.title or "",
                abstract=paper.abstract or "",
                body_text=body_text or paper.abstract or "",
                arxiv_id=paper.arxiv_id or str(paper.id),
            )
        except LlmError as exc:
            logger.warning("summarize_agent_fallback task_id=%s err=%s", task_id, exc)
            wiki = build_fallback_summary(
                title=paper.title or "",
                abstract=paper.abstract or "",
                body_text=body_text or paper.abstract or "",
                arxiv_id=paper.arxiv_id or str(paper.id),
            )
    else:
        logger.info("summarize_agent_disabled task_id=%s using local fallback", task_id)
        wiki = build_fallback_summary(
            title=paper.title or "",
            abstract=paper.abstract or "",
            body_text=body_text or paper.abstract or "",
            arxiv_id=paper.arxiv_id or str(paper.id),
        )

    _mark_running(session, task, paper, stage="graph")
    related = get_related_paper_payloads(session, paper)
    graph = GraphAgent(settings).run(
        paper_id=paper.id,
        title=paper.title or "",
        abstract=paper.abstract or "",
        arxiv_id=paper.arxiv_id or str(paper.id),
        primary_category=paper.primary_category or "",
        published_at=paper.published_at.isoformat() if paper.published_at else "",
        concepts=wiki.concepts,
        methods=wiki.methods,
        experiments=wiki.experiments,
        limitations=wiki.limitations,
        related_papers=related,
    )

    _mark_running(session, task, paper, stage="graph")
    related = _related_paper_payloads(session, paper)
    graph = GraphAgent(settings).run(
        paper_id=paper.id,
        title=paper.title or "",
        abstract=paper.abstract or "",
        arxiv_id=paper.arxiv_id or str(paper.id),
        primary_category=paper.primary_category or "",
        published_at=paper.published_at.isoformat() if paper.published_at else "",
        concepts=wiki.concepts,
        methods=wiki.methods,
        related_papers=related,
    )

    _mark_running(session, task, paper, stage="persist")
    chunks = _text_to_chunks(body_text or paper.abstract or "", max_chunks=80)
    result_rows = [*wiki.to_structured_rows(page_count=page_count), *graph.to_structured_rows()]
    results = [
        StructuredResultInput(
            result_type=row["result_type"],
            version=int(row.get("version") or 1),
            content_json=row["content_json"],
            source_locator={**(row.get("source_locator") or {}), "extract_source": source},
            confidence=row.get("confidence"),
        )
        for row in result_rows
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
        "parse_agent_succeeded task_id=%s paper_id=%s chunks=%s source=%s graph=%s",
        task_id,
        paper.id,
        len(chunk_inputs),
        source,
        graph.source,
    )
    payloads = []
    for item in papers:
        if item.id == paper.id:
            continue
        payloads.append(
            {
                "paper_id": item.id,
                "arxiv_id": item.arxiv_id or "",
                "title": item.title or "",
                "published_at": item.published_at.isoformat() if item.published_at else "",
                "primary_category": item.primary_category or "",
                "abstract": (item.abstract or "")[:400],
            }
        )
        if len(payloads) >= limit:
            break

    # If category filter emptied the list, retry without category
    if not payloads and paper.primary_category:
        papers, _ = list_papers(
            session,
            keyword=title[:80] if title else None,
            keywords=keywords[:8] or None,
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=1,
            page_size=max(limit + 2, 10),
        )
        for item in papers:
            if item.id == paper.id:
                continue
            payloads.append(
                {
                    "paper_id": item.id,
                    "arxiv_id": item.arxiv_id or "",
                    "title": item.title or "",
                    "published_at": item.published_at.isoformat() if item.published_at else "",
                    "primary_category": item.primary_category or "",
                    "abstract": (item.abstract or "")[:400],
                }
            )
            if len(payloads) >= limit:
                break
    return payloads


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
    # Prefer sentence boundaries to avoid mid-word quotes like "tworks that..."
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return [text[i : i + size].strip() for i in range(0, len(text), size) if text[i : i + size].strip()]

    pieces: list[str] = []
    buf = ""
    for sentence in sentences:
        candidate = f"{buf} {sentence}".strip() if buf else sentence
        if len(candidate) <= size:
            buf = candidate
            continue
        if buf:
            pieces.append(buf)
        if len(sentence) <= size:
            buf = sentence
        else:
            for i in range(0, len(sentence), size):
                part = sentence[i : i + size].strip()
                if part:
                    pieces.append(part)
            buf = ""
    if buf:
        pieces.append(buf)
    return pieces


__all__ = ["run_parse_agent_job"]
