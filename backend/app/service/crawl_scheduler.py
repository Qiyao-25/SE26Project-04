"""Background arXiv subscription crawl loop."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger("papermate.crawl_scheduler")


def _run_sync(engine, settings) -> dict:
    from app.service.subscriptions import sync_all_users

    with Session(engine) as session:
        return sync_all_users(session, max_per_subscription=3, settings=settings)


async def run_crawl_scheduler(app, stop_event: asyncio.Event) -> None:
    settings = app.state.settings
    if not settings.crawl_enabled:
        logger.info("crawl_scheduler_disabled")
        return

    interval = max(60, int(settings.crawl_interval_s))
    # Short initial delay so demo can see first tick without waiting full interval.
    initial_delay = min(30, interval)
    logger.info("crawl_scheduler_started interval_s=%s initial_delay_s=%s", interval, initial_delay)

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
        return
    except asyncio.TimeoutError:
        pass

    while not stop_event.is_set():
        try:
            stats = await asyncio.to_thread(_run_sync, app.state.engine, settings)
            logger.info("crawl_scheduler_tick %s", stats)
        except Exception:  # noqa: BLE001
            logger.exception("crawl_scheduler_failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            continue
