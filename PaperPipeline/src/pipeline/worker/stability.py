"""H077/H078 — retry, backoff, task log export on memory queue."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from ..schemas import TaskInput, TaskRecord, TaskStatus, TERMINAL_FAIL, TERMINAL_OK
from .memory_queue import MemoryTaskQueue

logger = logging.getLogger("pipeline.worker.stability")


class StableTaskQueue(MemoryTaskQueue):
    """Extends MemoryTaskQueue with retry/backoff and log export."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_base_s: float = 0.5,
        log_dir: Path | str = "data/logs",
    ) -> None:
        super().__init__(max_attempts=max_attempts)
        self.backoff_base_s = backoff_base_s
        self.log_dir = Path(log_dir)

    def execute_with_retry(self, task_id: str, *, simulate_fail_stage: str | None = None) -> TaskRecord:
        record = self._tasks[task_id]
        while record.attempts < self.max_attempts:
            record = self.execute(task_id, simulate_fail_stage=simulate_fail_stage)
            if record.status in TERMINAL_OK:
                self.export_log(record)
                return record
            if record.status in TERMINAL_FAIL and record.attempts >= self.max_attempts:
                self.export_log(record)
                return record
            delay = self.backoff_base_s * (2 ** (record.attempts - 1))
            logger.warning(
                "task_retry task_id=%s attempt=%s backoff_s=%.2f status=%s",
                task_id,
                record.attempts,
                delay,
                record.status.value,
            )
            time.sleep(delay)
            self._queue.appendleft(task_id)
            simulate_fail_stage = None  # only inject fail on first attempt
        self.export_log(record)
        return record

    def export_log(self, record: TaskRecord) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        path = self.log_dir / f"{record.task_id}.json"
        path.write_text(record.to_json(), encoding="utf-8")
        logger.info("task_log_exported path=%s status=%s", path, record.status.value)
        return path

    def run_scenario(self, name: str, task_input: TaskInput, *, simulate_fail_stage: str | None = None) -> TaskRecord:
        rec = self.create(task_input)
        logger.info("scenario=%s task_id=%s arxiv_id=%s", name, rec.task_id, task_input.arxiv_id)
        return self.execute_with_retry(rec.task_id, simulate_fail_stage=simulate_fail_stage)
