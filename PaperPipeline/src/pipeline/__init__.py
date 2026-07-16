"""PaperMate pipeline package (H037+).

Contract note (V0): Task / StructuredResult fields mirror Spike + H028.
When member A freezes OpenAPI/ADR, rename here only — do not widen silently.
"""

from .schemas import (
    StructuredResult,
    TaskInput,
    TaskRecord,
    TaskStatus,
    TaskStageTiming,
)

__all__ = [
    "StructuredResult",
    "TaskInput",
    "TaskRecord",
    "TaskStatus",
    "TaskStageTiming",
]
