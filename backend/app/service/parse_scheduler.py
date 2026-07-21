"""Background auto-parse: drain unparsed papers whenever any remain (newest first)."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import Paper, ParseTask

logger = logging.getLogger("papermate.parse_scheduler")


def _has_work(engine) -> bool:
    """True if any paper still needs parse or any task is already queued."""
    with Session(engine) as session:
        pending = session.scalar(
            select(Paper.id)
            .where(
                Paper.deleted_at.is_(None),
                Paper.ingest_status.in_(("metadata_only", "downloaded")),
            )
            .limit(1)
        )
        if pending is not None:
            return True
        queued = session.scalar(
            select(ParseTask.id).where(ParseTask.status == "queued").limit(1)
        )
        return queued is not None


def _enqueue_and_pick(engine, limit: int) -> list[int]:
    from app.service.tasks import enqueue_pending_tasks, list_tasks

    with Session(engine) as session:
        enqueue_pending_tasks(session, limit=limit)
        queued = list_tasks(session, status="queued", limit=limit)
        return [task.task_id for task in queued]


def _run_one(engine, task_id: int, settings) -> None:
    from app.service.parse_agent_runner import run_parse_agent_job

    run_parse_agent_job(engine, task_id, settings)


async def run_parse_scheduler(app, stop_event: asyncio.Event) -> None:
    """Parse continuously while unparsed papers remain; sleep only when the queue is empty."""
    settings = app.state.settings
    if not getattr(settings, "parse_scheduler_enabled", True):
        logger.info("parse_scheduler_disabled")
        return

    # Idle poll only applies when there is nothing left to parse.
    idle_interval = max(15, int(getattr(settings, "parse_scheduler_interval_s", 30)))
    batch = max(1, int(getattr(settings, "parse_scheduler_batch", 5)))
    initial_delay = min(10, idle_interval)
    logger.info(
        "parse_scheduler_started idle_interval_s=%s batch=%s initial_delay_s=%s",
        idle_interval,
        batch,
        initial_delay,
    )

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
        return
    except asyncio.TimeoutError:
        pass

    while not stop_event.is_set():
        try:
            while not stop_event.is_set() and await asyncio.to_thread(_has_work, app.state.engine):
                task_ids = await asyncio.to_thread(_enqueue_and_pick, app.state.engine, batch)
                if not task_ids:
                    # Work exists but nothing runnable yet (e.g. already running) — back off briefly.
                    break
                logger.info("parse_scheduler_running tasks=%s", task_ids)
                for task_id in task_ids[:batch]:
                    if stop_event.is_set():
                        break
                    try:
                        await asyncio.to_thread(_run_one, app.state.engine, task_id, settings)
                        logger.info("parse_scheduler_finished task_id=%s", task_id)
                    except Exception:  # noqa: BLE001
                        logger.exception("parse_scheduler_task_failed task_id=%s", task_id)
                # No idle sleep here: keep draining until unparsed papers are gone.
        except Exception:  # noqa: BLE001
            logger.exception("parse_scheduler_failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=idle_interval)
            return
        except asyncio.TimeoutError:
            continue
