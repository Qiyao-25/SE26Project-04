from pathlib import Path

import pytest

pytest.importorskip("fcntl")

from app.service.scheduler_lock import release_scheduler_lock, try_acquire_scheduler_lock


def test_scheduler_lock_allows_one_process_and_releases_cleanly(tmp_path: Path) -> None:
    first = try_acquire_scheduler_lock(tmp_path, "parse-scheduler")
    assert first is not None
    try:
        assert try_acquire_scheduler_lock(tmp_path, "parse-scheduler") is None
    finally:
        release_scheduler_lock(first)

    second = try_acquire_scheduler_lock(tmp_path, "parse-scheduler")
    assert second is not None
    release_scheduler_lock(second)
