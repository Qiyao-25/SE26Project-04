"""PaperMate pipeline package.

Contract note (V0): Task / StructuredResult fields mirror the pipeline contract.
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
