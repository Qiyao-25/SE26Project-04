"""Cross-process file locks for the in-process schedulers.

The production deployment is Linux-based, so ``fcntl.flock`` provides a
small dependency-free mutex shared by Uvicorn worker processes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

import fcntl


def try_acquire_scheduler_lock(lock_dir: str | Path, name: str) -> TextIO | None:
    directory = Path(lock_dir)
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / f"{name}.lock").open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def release_scheduler_lock(handle: TextIO | None) -> None:
    if handle is None:
        return
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()
