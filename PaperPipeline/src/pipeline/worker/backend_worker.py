"""Process queued backend parse tasks with the real PDF parser."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..agent import AgentCallError, AgentConfig, ChatAgent, build_structured_with_agent
from ..integration.backend_client import BackendClient
from ..integration.contracts import chunk_to_backend, wiki_to_backend_structured_rows
from ..parser.document import parse_document
from ..summarizer.struct_summary import build_structured

logger = logging.getLogger("pipeline.backend_worker")


class BackendParseWorker:
    """Single-worker adapter for the database-backed ParseTask queue."""

    def __init__(
        self,
        client: BackendClient,
        pdf_dir: Path,
        *,
        max_pages: int | None = None,
        min_chars: int = 500,
        html_dir: Path | None = None,
        prefer_html: bool = False,
    ) -> None:
        self.client = client
        self.pdf_dir = pdf_dir
        self.max_pages = max_pages
        self.min_chars = min_chars
        self.html_dir = html_dir or pdf_dir.parent / "worker_html"
        self.prefer_html = prefer_html
        self.agent = ChatAgent(AgentConfig.from_env())

    def run_once(self) -> dict[str, Any] | None:
        tasks = self.client.list_tasks(status="queued", limit=1)
        if not tasks:
            return None
        return self.process_task(tasks[0])

    def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = int(task["task_id"])
        paper_id = int(task["paper_id"])
        try:
            self.client.update_task(task_id, "running", stage="fetch")
            paper = self.client.get_paper(paper_id)
            arxiv_id = str(paper.get("arxiv_id") or "").strip()
            if not arxiv_id:
                raise WorkerFailure("PAPER_METADATA_INVALID", "论文缺少 arXiv ID")

            self.client.update_task(task_id, "running", stage="parse")
            parsed = parse_document(
                arxiv_id,
                self.pdf_dir,
                self.html_dir,
                pdf_url=paper.get("pdf_url"),
                html_url=f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}",
                max_pages=self.max_pages,
                min_chars=self.min_chars,
                prefer_html=self.prefer_html,
            )
            if not parsed.ok:
                raise WorkerFailure("PARSE_FAILED", parsed.error or "PDF 解析失败")

            self.client.update_task(task_id, "running", stage="summarize")
            try:
                wiki = (
                    build_structured_with_agent(
                        arxiv_id,
                        parsed.paragraphs,
                        title=str(paper.get("title") or ""),
                        abstract_hint=str(paper.get("abstract") or ""),
                        agent=self.agent,
                    )
                    if self.agent.ready
                    else build_structured(
                        arxiv_id,
                        parsed.paragraphs,
                        title=str(paper.get("title") or ""),
                        abstract_hint=str(paper.get("abstract") or ""),
                    )
                )
            except AgentCallError as exc:
                logger.warning("structured_agent_fallback task_id=%s detail=%s", task_id, exc)
                wiki = build_structured(
                    arxiv_id,
                    parsed.paragraphs,
                    title=str(paper.get("title") or ""),
                    abstract_hint=str(paper.get("abstract") or ""),
                )
            if not wiki.required_ok():
                raise WorkerFailure("STRUCTURED_RESULT_FAILED", "结构化摘要字段不完整")

            self.client.update_task(task_id, "running", stage="validate")
            chunks = [chunk_to_backend(asdict(paragraph)) for paragraph in parsed.paragraphs]
            self.client.update_task(task_id, "running", stage="persist")
            self.client.finalize_parse_result(
                task_id,
                chunks,
                wiki_to_backend_structured_rows(
                    summary=wiki.summary,
                    concept=wiki.concept,
                    methods=wiki.methods,
                    experiments=wiki.experiments,
                    limitations=wiki.limitations,
                    validation_flags=wiki.validation_flags,
                    page_count=parsed.page_count,
                    source=f"pipeline_{parsed.source_type}",
                ),
            )
            result = {"task_id": task_id, "paper_id": paper_id, "status": "succeeded", "stage": "completed", "source_type": parsed.source_type, "chunks": len(chunks), "validation_flags": wiki.validation_flags}
            logger.info("parse_task_succeeded task_id=%s paper_id=%s chunks=%s", task_id, paper_id, len(chunks))
            return result
        except WorkerFailure as exc:
            return self._fail(task_id, paper_id, exc.code, str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("parse_task_failed task_id=%s paper_id=%s", task_id, paper_id)
            return self._fail(task_id, paper_id, "WORKER_ERROR", str(exc))

    def _fail(self, task_id: int, paper_id: int, code: str, detail: str) -> dict[str, Any]:
        try:
            self.client.update_task(task_id, "failed", code, stage="failed")
        except Exception:  # noqa: BLE001
            logger.exception("parse_task_failure_writeback_failed task_id=%s", task_id)
        logger.error("parse_task_failed task_id=%s paper_id=%s code=%s detail=%s", task_id, paper_id, code, detail)
        return {"task_id": task_id, "paper_id": paper_id, "status": "failed", "error_code": code, "detail": detail}


class WorkerFailure(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


__all__ = ["BackendParseWorker", "WorkerFailure"]
