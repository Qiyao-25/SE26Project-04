""" · In-memory task queue: create → execute → success/failure.

Logs task_id and per-stage elapsed time (Spike/ aligned).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from typing import Deque

from ..crawler import fetch_paper
from ..parser import parse_pdf
from ..schemas import (
    StructuredResult,
    TaskInput,
    TaskRecord,
    TaskStageTiming,
    TaskStatus,
)
from ..schemas import TERMINAL_OK
from ..summarizer import summarize

logger = logging.getLogger("pipeline.worker")


class MemoryTaskQueue:
    """Minimal in-process queue + store (no Redis / no DB)."""

    def __init__(self, max_attempts: int = 3) -> None:
        self._queue: Deque[str] = deque()
        self._tasks: dict[str, TaskRecord] = {}
        self._by_key: dict[str, str] = {}
        self.max_attempts = max_attempts

    def create(self, task_input: TaskInput) -> TaskRecord:
        key = task_input.idempotency_key()
        if not task_input.force and key in self._by_key:
            existing = self._tasks[self._by_key[key]]
            if existing.status in TERMINAL_OK:
                logger.info(
                    "idempotent_hit task_id=%s key=%s status=%s",
                    existing.task_id,
                    key,
                    existing.status.value,
                )
                return existing

        task_id = f"tsk_{uuid.uuid4().hex[:10]}"
        record = TaskRecord(task_id=task_id, input=task_input, status=TaskStatus.PENDING)
        self._tasks[task_id] = record
        self._by_key[key] = task_id
        self._queue.append(task_id)
        logger.info(
            "task_created task_id=%s arxiv_id=%s key=%s status=%s",
            task_id,
            task_input.arxiv_id,
            key,
            record.status.value,
        )
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def pending_count(self) -> int:
        return len(self._queue)

    def run_once(self, *, simulate_fail_stage: str | None = None) -> TaskRecord | None:
        if not self._queue:
            return None
        task_id = self._queue.popleft()
        return self.execute(task_id, simulate_fail_stage=simulate_fail_stage)

    def drain(self, *, simulate_fail_stage: str | None = None) -> list[TaskRecord]:
        done: list[TaskRecord] = []
        while self._queue:
            rec = self.run_once(simulate_fail_stage=simulate_fail_stage)
            if rec:
                done.append(rec)
        return done

    def execute(self, task_id: str, *, simulate_fail_stage: str | None = None) -> TaskRecord:
        record = self._tasks[task_id]
        record.attempts += 1
        logger.info(
            "task_execute_start task_id=%s attempt=%s/%s arxiv_id=%s",
            task_id,
            record.attempts,
            self.max_attempts,
            record.input.arxiv_id,
        )

        try:
            self._run_pipeline(record, simulate_fail_stage=simulate_fail_stage)
        except Exception as exc:  # noqa: BLE001
            record.error = str(exc)
            record.touch(TaskStatus.FAILED)
            logger.exception("task_execute_crash task_id=%s error=%s", task_id, exc)

        self._log_summary(record)
        return record

    def _run_pipeline(self, record: TaskRecord, *, simulate_fail_stage: str | None) -> None:
        arxiv_id = record.input.arxiv_id

        record.touch(TaskStatus.FETCHING)
        t0 = time.perf_counter()
        fetch = fetch_paper(arxiv_id, fail=(simulate_fail_stage == "fetch"))
        elapsed = round(time.perf_counter() - t0, 4)
        record.stage_timings.append(
            TaskStageTiming("fetch", elapsed, "ok" if fetch.ok else "failed", fetch.error or "")
        )
        logger.info(
            "stage=fetch task_id=%s elapsed_s=%.4f status=%s",
            record.task_id,
            elapsed,
            "ok" if fetch.ok else "failed",
        )
        if not fetch.ok:
            record.error = fetch.error
            record.touch(TaskStatus.FETCH_FAILED)
            return
        record.touch(TaskStatus.FETCHED)

        record.touch(TaskStatus.PARSING)
        t0 = time.perf_counter()
        parsed = parse_pdf(arxiv_id, fetch.pdf_path, fail=(simulate_fail_stage == "parse"))
        elapsed = round(time.perf_counter() - t0, 4)
        record.stage_timings.append(
            TaskStageTiming("parse", elapsed, "ok" if parsed.ok else "failed", parsed.error or "")
        )
        logger.info(
            "stage=parse task_id=%s elapsed_s=%.4f status=%s",
            record.task_id,
            elapsed,
            "ok" if parsed.ok else "failed",
        )
        if not parsed.ok:
            record.error = parsed.error
            record.touch(TaskStatus.PARSE_FAILED)
            return
        record.touch(TaskStatus.PARSED_DEGRADED if parsed.degraded else TaskStatus.PARSED)

        record.touch(TaskStatus.SUMMARIZING)
        t0 = time.perf_counter()
        summ = summarize(
            arxiv_id,
            parsed.chunks,
            fetch.abstract,
            fail=(simulate_fail_stage == "summarize"),
        )
        elapsed = round(time.perf_counter() - t0, 4)
        record.stage_timings.append(
            TaskStageTiming("summarize", elapsed, "ok" if summ.ok else "failed", summ.error or "")
        )
        logger.info(
            "stage=summarize task_id=%s elapsed_s=%.4f status=%s",
            record.task_id,
            elapsed,
            "ok" if summ.ok else "failed",
        )
        if not summ.ok:
            record.error = summ.error
            record.touch(TaskStatus.SUMMARIZE_FAILED)
            return

        record.result = StructuredResult(
            arxiv_id=arxiv_id,
            summary=summ.summary,
            concept=summ.concept,
            methods=summ.methods,
            pdf_path=fetch.pdf_path,
            chunk_count=len(parsed.chunks),
            meta={"title": fetch.title, "authors": fetch.authors},
        )
        record.touch(TaskStatus.SUMMARIZED)
        record.local_fallback = True
        record.touch(TaskStatus.QA_READY)

    def _log_summary(self, record: TaskRecord) -> None:
        total = round(sum(t.elapsed_s for t in record.stage_timings), 4)
        logger.info(
            "task_execute_done task_id=%s status=%s attempts=%s total_stage_s=%.4f error=%s",
            record.task_id,
            record.status.value,
            record.attempts,
            total,
            record.error,
        )
        for t in record.stage_timings:
            logger.info(
                "task_id=%s stage_timing stage=%s elapsed_s=%.4f status=%s detail=%s",
                record.task_id,
                t.stage,
                t.elapsed_s,
                t.status,
                t.detail,
            )
