from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.model import ParseTask, Paper, StructuredResult
from app.schema.papers import (
    StructuredResultBatch,
    TaskResponse,
    TaskUpdate,
)


TASK_STATUSES = {"queued", "running", "succeeded", "failed", "timed_out"}


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
        return to_task(active), False

    task = ParseTask(paper_id=paper_id, task_type=task_type, status="queued", attempt=1, idempotency_key=idempotency_key)
    session.add(task)
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


def update_task(session: Session, task_id: int, payload: TaskUpdate) -> TaskResponse:
    task = session.get(ParseTask, task_id)
    if task is None:
        raise ValueError("TASK_NOT_FOUND")
    if payload.status == "running" and task.status == "queued":
        task.started_at = task.started_at or _now()
    if payload.status in {"failed", "timed_out"}:
        task.finished_at = _now()
    task.status = payload.status
    task.error_code = payload.error_code
    session.commit()
    session.refresh(task)
    return to_task(task)


def save_results(session: Session, task_id: int, payload: StructuredResultBatch) -> TaskResponse:
    task = session.get(ParseTask, task_id)
    if task is None:
        raise ValueError("TASK_NOT_FOUND")
    if task.status in {"failed", "timed_out"}:
        raise ValueError("TASK_CONFLICT")

    task.started_at = task.started_at or _now()
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
    task.status = "succeeded"
    task.finished_at = _now()
    task.error_code = None
    paper = session.get(Paper, task.paper_id)
    paper.ingest_status = "parsed"
    session.commit()
    session.refresh(task)
    return to_task(task)
