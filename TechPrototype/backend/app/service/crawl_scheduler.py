"""Background arXiv subscription crawl loop."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session


logger = logging.getLogger("papermate.crawl_scheduler")


def _run_sync(engine, settings) -> dict:
    from app.service.subscriptions import sync_all_users

    with Session(engine) as session:
        return sync_all_users(session, max_per_subscription=5, settings=settings)


async def run_crawl_scheduler(app, stop_event: asyncio.Event) -> None:
    settings = app.state.settings
    # Always keep the loop alive so admin can toggle crawl_enabled / interval at runtime.
    interval = max(60, int(settings.crawl_interval_s))
    initial_delay = min(30, interval)
    logger.info(
        "crawl_scheduler_started interval_s=%s enabled=%s initial_delay_s=%s",
        interval,
        bool(settings.crawl_enabled),
        initial_delay,
    )

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
        return
    except asyncio.TimeoutError:
        pass

    while not stop_event.is_set():
        enabled = bool(settings.crawl_enabled)
        interval = max(60, int(settings.crawl_interval_s))
        if enabled:
            try:
                stats = await asyncio.to_thread(_run_sync, app.state.engine, settings)
                logger.info("crawl_scheduler_tick %s", stats)
            except Exception:  # noqa: BLE001
                logger.exception("crawl_scheduler_failed")
        else:
            logger.info("crawl_scheduler_skipped_disabled next_wait_s=%s", interval)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            continue
