"""Background parse runner: fetch text → Summarize Agent → persist Wiki + chunks."""

from __future__ import annotations

import logging
import re
import tempfile
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.agents.llm_client import LlmError
from app.agents.summarize_agent import SummarizeAgent, build_fallback_summary
from app.agents.graph_agent import GraphAgent
from app.core.config import Settings, get_settings
from app.model import ParseTask, Paper
from app.schema.papers import ParseResultCommit, StructuredResultInput, TextChunkInput
from app.service.content_validator import ContentValidationAgent
from app.service.papers import get_related_paper_payloads
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

    _mark_running(session, task, paper, stage="validate")
    body_chars = len((body_text or paper.abstract or "").strip())
    report = ContentValidationAgent().validate_wiki(
        summary=wiki.summary,
        concepts=wiki.concepts,
        methods=wiki.methods,
        experiments=wiki.experiments,
        limitations=wiki.limitations,
        page_count=page_count,
        body_chars=body_chars,
        existing_flags=wiki.validation_flags,
        source=wiki.source,
    )
    wiki.validation_flags = report.flags

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

    _mark_running(session, task, paper, stage="persist")
    chunks = _text_to_chunks(body_text or paper.abstract or "", max_chunks=80)
    result_rows = [
        *wiki.to_structured_rows(page_count=page_count, uncertain_fields=report.uncertain_fields),
        *graph.to_structured_rows(),
    ]
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
    """Prefer PDF text; fall back to ar5iv/HTML; finally abstract."""
    pdf_url = (paper.pdf_url or "").strip()
    if not pdf_url and paper.arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{paper.arxiv_id}.pdf"

    if pdf_url:
        try:
            text, pages = _download_and_extract_pdf(pdf_url, max_pages=settings.parse_agent_max_pages)
            if len(text.strip()) >= 400:
                return text, pages, "pdf"
            if text.strip():
                logger.info("pdf_text_short arxiv_id=%s chars=%s; try_html", paper.arxiv_id, len(text.strip()))
        except Exception as exc:  # noqa: BLE001
            logger.warning("pdf_extract_failed arxiv_id=%s err=%s", paper.arxiv_id, exc)

    html_url = ""
    if paper.arxiv_id:
        html_url = f"https://ar5iv.labs.arxiv.org/html/{paper.arxiv_id}"
    source_url = (paper.source_url or "").strip()
    if source_url and "html" in source_url.casefold():
        html_url = source_url

    if html_url:
        try:
            text, sections = _download_and_extract_html(html_url, max_chars=120_000)
            if len(text.strip()) >= 200:
                return text, max(sections, 1), "html"
        except Exception as exc:  # noqa: BLE001
            logger.warning("html_extract_failed arxiv_id=%s err=%s", paper.arxiv_id, exc)

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


class _Ar5ivHtmlParser(HTMLParser):
    """Lightweight ar5iv/HTML body extractor (stdlib only)."""

    _BLOCK = {"article", "div", "li", "p", "section", "td", "th"}
    _HEADING = {"h1", "h2", "h3", "h4", "h5", "h6"}
    _SKIP = {"script", "style", "svg", "noscript", "nav", "footer", "header"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.section = "body"
        self._skip_depth = 0
        self._buffer: list[str] = []
        self.paragraphs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        tag = tag.lower()
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self._HEADING or tag in self._BLOCK:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self._HEADING:
            text = re.sub(r"\s+", " ", " ".join(self._buffer)).strip()
            self._buffer.clear()
            if text:
                self.section = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", text).strip()[:64] or "body"
        elif tag in self._BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self._buffer.append(data)

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", " ".join(self._buffer)).strip()
        self._buffer.clear()
        if len(text) >= 40:
            self.paragraphs.append((self.section, text[:2000]))


def _download_and_extract_html(url: str, *, max_chars: int = 120_000) -> tuple[str, int]:
    request = urllib.request.Request(url, headers={"User-Agent": "PaperMate-ParseAgent/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    html = raw.decode("utf-8", errors="replace")
    parser = _Ar5ivHtmlParser()
    parser.feed(html)
    parser.close()
    parts: list[str] = []
    total = 0
    for section, body in parser.paragraphs:
        piece = f"[section: {section}] {body}"
        if total + len(piece) > max_chars:
            break
        parts.append(piece)
        total += len(piece) + 2
    return "\n\n".join(parts), len(parts)


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
                        "section": _guess_section(piece),
                        "content": piece,
                    }
                )
        return chunks

    # HTML section markers from ar5iv extract
    section_blocks = re.split(r"\[section:\s*([^\]]+)\]\s*", cleaned)
    if len(section_blocks) > 1:
        it = iter(section_blocks[1:])
        for section_name, body in zip(it, it):
            section = (section_name or "body").strip()[:64] or "body"
            for piece in _split_pieces(body, size=700):
                if len(chunks) >= max_chunks:
                    return chunks
                chunks.append(
                    {
                        "chunk_id": f"s-{len(chunks) + 1}",
                        "page_no": 1,
                        "section": section,
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
                "section": _guess_section(piece),
                "content": piece,
            }
        )
    return chunks


def _guess_section(text: str) -> str:
    head = (text or "")[:220].casefold()
    rules = (
        (("abstract", "摘要"), "abstract"),
        (("introduction", "引言", "背景"), "introduction"),
        (("related work", "related works", "相关工作"), "related_work"),
        (("method", "approach", "architecture", "模型", "方法"), "method"),
        (("experiment", "evaluation", "result", "实验", "结果"), "experiments"),
        (("limitation", "discussion", "conclusion", "局限", "讨论", "结论"), "discussion"),
    )
    for keywords, label in rules:
        if any(keyword in head for keyword in keywords):
            return label
    return "body"


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
