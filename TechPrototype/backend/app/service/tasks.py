from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.model import ParseTask, Paper, StructuredResult, TextChunk
from app.schema.papers import (
    ParseResultCommit,
    StructuredResultBatch,
    TaskResponse,
    TaskUpdate,
    TextChunkBatch,
)


TASK_STATUSES = {"queued", "running", "succeeded", "failed", "timed_out"}
# 首次失败后允许再试 1 次；第二次仍失败则由解析 runner 软删论文。
MAX_ATTEMPTS = 2
ALLOWED_TRANSITIONS = {
    "queued": {"running"},
    "running": {"running", "failed", "timed_out"},
    "succeeded": set(),
    "failed": set(),
    "timed_out": set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def to_task(task: ParseTask) -> TaskResponse:
    return TaskResponse(
        task_id=task.id,
        paper_id=task.paper_id,
        task_type=task.task_type,
        status=task.status,
        attempt=task.attempt,
        idempotency_key=task.idempotency_key,
        requested_at=task.requested_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        error_code=task.error_code,
        stage=task.stage,
        retryable=task.status in {"failed", "timed_out"} and task.attempt < MAX_ATTEMPTS,
    )


def create_task(session: Session, paper_id: int, task_type: str, idempotency_key: str, force: bool = False) -> tuple[TaskResponse, bool]:
    paper = session.get(Paper, paper_id)
    if paper is None or paper.deleted_at is not None:
        raise ValueError("PAPER_NOT_FOUND")
    existing = session.scalar(select(ParseTask).where(ParseTask.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.paper_id != paper_id:
            raise ValueError("TASK_CONFLICT")
        return to_task(existing), False

    active = session.scalar(
        select(ParseTask)
        .where(ParseTask.paper_id == paper_id, ParseTask.status.in_(("queued", "running")))
        .order_by(ParseTask.requested_at.desc(), ParseTask.id.desc())
    )
    if active is not None:
        if not force:
            return to_task(active), False
        # force 重新解析：将进行中的任务标记失败，允许新建
        active.status = "failed"
        active.error_code = "SUPERSEDED"
        active.finished_at = _now()
        active.stage = "failed"

    task = ParseTask(paper_id=paper_id, task_type=task_type, status="queued", attempt=1, idempotency_key=idempotency_key)
    session.add(task)
    paper.ingest_status = "queued"
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("TASK_CONFLICT") from exc
    session.refresh(task)
    return to_task(task), True


def get_task(session: Session, task_id: int) -> TaskResponse:
    task = session.get(ParseTask, task_id)
    if task is None:
        raise ValueError("TASK_NOT_FOUND")
    return to_task(task)


def list_tasks(session: Session, status: str | None = None, limit: int = 20) -> list[TaskResponse]:
    stmt = select(ParseTask).order_by(ParseTask.requested_at.asc(), ParseTask.id.asc()).limit(limit)
    if status is not None:
        if status not in TASK_STATUSES:
            raise ValueError("TASK_STATUS_INVALID")
        stmt = stmt.where(ParseTask.status == status)
    return [to_task(task) for task in session.scalars(stmt).all()]


def claim_task(session: Session, worker_id: str) -> TaskResponse | None:
    """Atomically claim the oldest queued task for one Worker."""
    if not worker_id.strip():
        raise ValueError("WORKER_ID_INVALID")
    for _ in range(3):
        task_id = session.scalar(
            select(ParseTask.id)
            .where(ParseTask.status == "queued")
            .order_by(ParseTask.requested_at.asc(), ParseTask.id.asc())
            .limit(1)
        )
        if task_id is None:
            return None

        now = _now()
        result = session.execute(
            update(ParseTask)
            .where(ParseTask.id == task_id, ParseTask.status == "queued")
            .values(status="running", started_at=now, stage="fetch", error_code=None)
        )
        if result.rowcount != 1:
            session.rollback()
            continue

        task = session.get(ParseTask, task_id)
        paper = session.get(Paper, task.paper_id) if task else None
        if paper is not None:
            paper.ingest_status = "parsing"
        session.commit()
        session.refresh(task)
        return to_task(task)
    return None


def queue_stats(session: Session, stale_after_seconds: int = 900) -> dict:
    counts = {
        status: session.scalar(select(func.count(ParseTask.id)).where(ParseTask.status == status)) or 0
        for status in sorted(TASK_STATUSES)
    }
    cutoff = _now() - timedelta(seconds=stale_after_seconds)
    stale_running = session.scalar(
        select(func.count(ParseTask.id)).where(
            ParseTask.status == "running",
            ParseTask.started_at.is_not(None),
            ParseTask.started_at < cutoff,
        )
    ) or 0
    retryable_failed = session.scalar(
        select(func.count(ParseTask.id)).where(
            ParseTask.status.in_(("failed", "timed_out")),
            ParseTask.attempt < MAX_ATTEMPTS,
        )
    ) or 0
    oldest_queued_at = session.scalar(
        select(func.min(ParseTask.requested_at)).where(ParseTask.status == "queued")
    )
    return {
        "counts": counts,
        "retryable_failed": retryable_failed,
        "stale_running": stale_running,
        "oldest_queued_at": oldest_queued_at,
    }


def update_task(session: Session, task_id: int, payload: TaskUpdate) -> TaskResponse:
    task = session.get(ParseTask, task_id)
    if task is None:
        raise ValueError("TASK_NOT_FOUND")
    if payload.status not in ALLOWED_TRANSITIONS.get(task.status, set()):
        raise ValueError("TASK_STATE_CONFLICT")
    if payload.status == "running" and task.status == "queued":
        task.started_at = task.started_at or _now()
    if payload.stage:
        task.stage = payload.stage
    if payload.status in {"failed", "timed_out"}:
        task.finished_at = _now()
    paper = session.get(Paper, task.paper_id)
    if paper is not None:
        if payload.status == "running":
            paper.ingest_status = "parsing"
        elif payload.status in {"failed", "timed_out"}:
            paper.ingest_status = "failed"
    task.status = payload.status
    task.error_code = payload.error_code
    session.commit()
    session.refresh(task)
    return to_task(task)


def _get_active_task(session: Session, task_id: int) -> ParseTask:
    task = session.get(ParseTask, task_id)
    if task is None:
        raise ValueError("TASK_NOT_FOUND")
    if task.status not in {"queued", "running"}:
        raise ValueError("TASK_CONFLICT")
    return task

def _write_structured_results(session: Session, task: ParseTask, payload: StructuredResultBatch) -> None:
    for item in payload.results:
        result = session.scalar(
            select(StructuredResult).where(
                StructuredResult.paper_id == task.paper_id,
                StructuredResult.result_type == item.result_type,
                StructuredResult.version == item.version,
            )
        )
        if result is None:
            result = StructuredResult(
                paper_id=task.paper_id,
                parse_task_id=task.id,
                result_type=item.result_type,
                version=item.version,
                content_json=item.content_json,
                source_locator=item.source_locator,
                confidence=item.confidence,
            )
            session.add(result)
        else:
            result.parse_task_id = task.id
            result.content_json = item.content_json
            result.source_locator = item.source_locator
            result.confidence = item.confidence

def _complete_task(session: Session, task: ParseTask) -> TaskResponse:
    task.started_at = task.started_at or _now()
    chunk_count = session.scalar(
        select(func.count(TextChunk.id)).where(TextChunk.paper_id == task.paper_id)
    ) or 0
    task.status = "succeeded"
    task.finished_at = _now()
    task.error_code = None
    task.stage = "completed"
    paper = session.get(Paper, task.paper_id)
    paper.chunk_count = chunk_count
    paper.ingest_status = "qa_ready" if chunk_count > 0 else "parsed"
    session.commit()
    session.refresh(task)
    return to_task(task)


def save_results(session: Session, task_id: int, payload: StructuredResultBatch) -> TaskResponse:
    task = _get_active_task(session, task_id)
    task.started_at = task.started_at or _now()
    _write_structured_results(session, task, payload)
    return _complete_task(session, task)


def save_parse_result(session: Session, task_id: int, payload: ParseResultCommit) -> TaskResponse:
    from app.repository.chunks import replace_chunks

    task = _get_active_task(session, task_id)
    replace_chunks(session, task.paper_id, TextChunkBatch(chunks=payload.chunks))
    _write_structured_results(
        session,
        task,
        StructuredResultBatch(results=payload.results),
    )
    return _complete_task(session, task)


def retry_task(session: Session, task_id: int) -> TaskResponse:
    task = session.get(ParseTask, task_id)
    if task is None:
        raise ValueError("TASK_NOT_FOUND")
    if task.status not in {"failed", "timed_out"}:
        raise ValueError("TASK_RETRY_CONFLICT")
    if task.attempt >= MAX_ATTEMPTS:
        raise ValueError("TASK_RETRY_EXHAUSTED")

    task.status = "queued"
    task.attempt += 1
    task.requested_at = _now()
    task.started_at = None
    task.finished_at = None
    task.error_code = None
    task.stage = None
    paper = session.get(Paper, task.paper_id)
    if paper is not None:
        paper.ingest_status = "queued"
    session.commit()
    session.refresh(task)
    return to_task(task)


def _bump_queued_to_front(session: Session, task: ParseTask) -> ParseTask:
    """Move an existing queued task ahead of all other queued tasks (no new row)."""
    oldest = session.scalar(select(func.min(ParseTask.requested_at)).where(ParseTask.status == "queued"))
    if oldest is None:
        task.requested_at = _now() - timedelta(days=365)
    else:
        # Keep strictly before current head so claim/scheduler picks this first.
        task.requested_at = oldest - timedelta(milliseconds=1)
    session.commit()
    session.refresh(task)
    return task


def boost_parse_priority(session: Session, paper_id: int) -> tuple[TaskResponse, bool]:
    """Raise priority of this paper's parse job without spawning duplicate tasks.

    Returns (task, should_start_runner).
    - Reuses queued/running tasks (bumps queued to front).
    - Retries a failed/timed_out task in place when still retryable.
    - Creates at most one task via stable idempotency key if none exists.
    """
    paper = session.get(Paper, paper_id)
    if paper is None or paper.deleted_at is not None:
        raise ValueError("PAPER_NOT_FOUND")
    if paper.ingest_status in {"parsed", "qa_ready"}:
        raise ValueError("PAPER_ALREADY_PARSED")

    active = session.scalar(
        select(ParseTask)
        .where(ParseTask.paper_id == paper_id, ParseTask.status.in_(("queued", "running")))
        .order_by(ParseTask.requested_at.desc(), ParseTask.id.desc())
    )
    if active is not None:
        if active.status == "running":
            return to_task(active), False
        paper.ingest_status = "queued"
        active = _bump_queued_to_front(session, active)
        return to_task(active), True

    latest = session.scalar(
        select(ParseTask)
        .where(ParseTask.paper_id == paper_id)
        .order_by(ParseTask.requested_at.desc(), ParseTask.id.desc())
    )
    if latest is not None and latest.status in {"failed", "timed_out"}:
        if latest.attempt >= MAX_ATTEMPTS:
            raise ValueError("TASK_RETRY_EXHAUSTED")
        retried = retry_task(session, latest.id)
        task = session.get(ParseTask, retried.task_id)
        assert task is not None
        task = _bump_queued_to_front(session, task)
        return to_task(task), True

    if latest is not None and latest.status == "succeeded":
        raise ValueError("PAPER_ALREADY_PARSED")

    # Stable key: repeated clicks reuse this row instead of flooding the queue.
    task, _created = create_task(
        session,
        paper_id,
        "full_parse",
        f"user-priority:{paper_id}",
        force=False,
    )
    if task.status == "running":
        return task, False
    if task.status == "queued":
        row = session.get(ParseTask, task.task_id)
        assert row is not None
        row = _bump_queued_to_front(session, row)
        return to_task(row), True
    raise ValueError("TASK_CONFLICT")


def delete_task(session: Session, task_id: int) -> dict:
    task = session.get(ParseTask, task_id)
    if task is None:
        raise ValueError("TASK_NOT_FOUND")
    if task.status == "running":
        raise ValueError("TASK_DELETE_CONFLICT")
    paper_id = task.paper_id
    session.delete(task)
    session.commit()
    return {"deleted": True, "task_id": task_id, "paper_id": paper_id}


def recover_stale_tasks(session: Session, stale_after_seconds: int = 900) -> list[TaskResponse]:
    cutoff = _now() - timedelta(seconds=stale_after_seconds)
    tasks = session.scalars(
        select(ParseTask).where(
            ParseTask.status == "running",
            ParseTask.started_at.is_not(None),
            ParseTask.started_at < cutoff,
        )
    ).all()
    for task in tasks:
        task.status = "timed_out"
        task.error_code = "STALE_TASK"
        task.stage = "failed"
        task.finished_at = _now()
        paper = session.get(Paper, task.paper_id)
        if paper is not None:
            paper.ingest_status = "failed"
            if task.attempt >= MAX_ATTEMPTS and paper.deleted_at is None:
                paper.deleted_at = _now()
    if tasks:
        session.commit()
    return [to_task(task) for task in tasks]


def enqueue_pending_tasks(session: Session, limit: int = 20) -> list[TaskResponse]:
    # Newest ingested papers first.
    papers = session.scalars(
        select(Paper)
        .where(Paper.deleted_at.is_(None), Paper.ingest_status.in_(("metadata_only", "downloaded")))
        .order_by(Paper.created_at.desc().nullslast(), Paper.id.desc())
        .limit(limit)
    ).all()
    queued: list[TaskResponse] = []
    for paper in papers:
        active = session.scalar(
            select(ParseTask).where(
                ParseTask.paper_id == paper.id,
                ParseTask.status.in_(("queued", "running")),
            )
        )
        if active is not None:
            queued.append(to_task(active))
            continue

        latest = session.scalar(
            select(ParseTask)
            .where(ParseTask.paper_id == paper.id)
            .order_by(ParseTask.requested_at.desc(), ParseTask.id.desc())
        )
        if latest is not None and latest.status in {"failed", "timed_out"}:
            if latest.attempt < MAX_ATTEMPTS:
                queued.append(retry_task(session, latest.id))
            continue

        task = ParseTask(
            paper_id=paper.id,
            task_type="full_parse",
            status="queued",
            attempt=1,
            idempotency_key=f"auto-parse:{paper.id}:v1",
        )
        paper.ingest_status = "queued"
        session.add(task)
        session.flush()
        queued.append(to_task(task))
    if papers:
        session.commit()
        for task in queued:
            session.refresh(session.get(ParseTask, task.task_id))
    return queued
