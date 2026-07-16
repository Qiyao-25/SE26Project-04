"""H037 · Task / status / result schemas (contract V0).

Aligned with:
- Spike states in docs/spike/技术Spike清单.md
- backend/app/model/entities.py (ParseTask / StructuredResult / TextChunk)
- UIPrototype mocks via integration/contracts.py adapters

Status dual-track:
- Pipeline TaskStatus: fetching → parsed → summarized → qa_ready (granular)
- ORM ParseTask.status: queued | running | succeeded | failed
  (see pipeline_status_to_orm in integration/contracts.py)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import hashlib
import json


class TaskStatus(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    FETCHED = "fetched"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSED_DEGRADED = "parsed_degraded"
    SUMMARIZING = "summarizing"
    SUMMARIZED = "summarized"
    QA_READY = "qa_ready"
    FETCH_FAILED = "fetch_failed"
    PARSE_FAILED = "parse_failed"
    PARSE_TIMEOUT = "parse_timeout"
    SUMMARIZE_FAILED = "summarize_failed"
    FAILED = "failed"  # generic terminal for demo queue


TERMINAL_OK = {TaskStatus.QA_READY, TaskStatus.SUMMARIZED}
TERMINAL_FAIL = {
    TaskStatus.FETCH_FAILED,
    TaskStatus.PARSE_FAILED,
    TaskStatus.PARSE_TIMEOUT,
    TaskStatus.SUMMARIZE_FAILED,
    TaskStatus.FAILED,
}


@dataclass
class TaskInput:
    """Worker 入队输入。"""

    arxiv_id: str
    pipeline_ver: str = "v0"
    keyword: str | None = None
    force: bool = False  # True 时忽略幂等命中

    def idempotency_key(self) -> str:
        raw = f"{self.arxiv_id}:{self.pipeline_ver}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class TaskStageTiming:
    stage: str
    elapsed_s: float
    status: str
    detail: str = ""


@dataclass
class StructuredResult:
    """摘要三件套（管线侧扁平结构）。

    写入 ORM 时用 wiki_to_backend_structured() → content_json + source_locator。
    供给前端时用 wiki_to_ui_summary() → paper-summary.json 形状。
    """

    arxiv_id: str
    summary: str = ""
    concept: str = ""
    methods: str = ""
    pdf_path: str | None = None
    chunk_count: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def required_ok(self) -> bool:
        return bool(self.summary and self.concept and self.methods)


@dataclass
class TaskRecord:
    task_id: str
    input: TaskInput
    status: TaskStatus = TaskStatus.PENDING
    idempotency_key: str = ""
    attempts: int = 0
    created_at: str = ""
    updated_at: str = ""
    stage_timings: list[TaskStageTiming] = field(default_factory=list)
    result: StructuredResult | None = None
    error: str | None = None
    local_fallback: bool = False

    def __post_init__(self) -> None:
        now = _now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.idempotency_key:
            self.idempotency_key = self.input.idempotency_key()

    def touch(self, status: TaskStatus | None = None) -> None:
        if status is not None:
            self.status = status
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "attempts": self.attempts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "input": asdict(self.input),
            "stage_timings": [asdict(t) for t in self.stage_timings],
            "result": asdict(self.result) if self.result else None,
            "error": self.error,
            "local_fallback": self.local_fallback,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
