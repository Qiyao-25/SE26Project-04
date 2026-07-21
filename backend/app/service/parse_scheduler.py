"""Background auto-parse of unparsed papers (newest first)."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger("papermate.parse_scheduler")


def _enqueue_and_pick(engine, limit: int) -> list[int]:
    from app.service.tasks import enqueue_pending_tasks, list_tasks

    with Session(engine) as session:
        enqueue_pending_tasks(session, limit=limit)
        queued = list_tasks(session, status="queued", limit=limit)
        # Prefer newest paper ids (enqueue already orders newest-first for pending).
        return [task.task_id for task in queued]


def _run_one(engine, task_id: int, settings) -> None:
    from app.service.parse_agent_runner import run_parse_agent_job

    run_parse_agent_job(engine, task_id, settings)


async def run_parse_scheduler(app, stop_event: asyncio.Event) -> None:
    settings = app.state.settings
    if not getattr(settings, "parse_scheduler_enabled", True):
        logger.info("parse_scheduler_disabled")
        return

    interval = max(30, int(getattr(settings, "parse_scheduler_interval_s", 120)))
    batch = max(1, int(getattr(settings, "parse_scheduler_batch", 3)))
    initial_delay = min(20, interval)
    logger.info(
        "parse_scheduler_started interval_s=%s batch=%s initial_delay_s=%s",
        interval,
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
            task_ids = await asyncio.to_thread(_enqueue_and_pick, app.state.engine, batch)
            logger.info("parse_scheduler_enqueued tasks=%s", task_ids)
            for task_id in task_ids[:batch]:
                if stop_event.is_set():
                    break
                try:
                    await asyncio.to_thread(_run_one, app.state.engine, task_id, settings)
                    logger.info("parse_scheduler_finished task_id=%s", task_id)
                except Exception:  # noqa: BLE001
                    logger.exception("parse_scheduler_task_failed task_id=%s", task_id)
        except Exception:  # noqa: BLE001
            logger.exception("parse_scheduler_failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            continue
