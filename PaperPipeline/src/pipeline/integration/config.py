"""Integration config — central place to align with C/A/E when their deliverables land."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class IntegrationConfig:
    api_base: str = ""
    qa_mode: str = "sample"  # sample | remote
    chunks_mode: str = "local"  # local | remote
    samples_dir: str = "data/samples"

    @classmethod
    def from_env(cls) -> "IntegrationConfig":
        return cls(
            api_base=(os.environ.get("PAPERMATE_API_BASE") or "").rstrip("/"),
            qa_mode=os.environ.get("PAPERMATE_QA_MODE", "sample"),
            chunks_mode="remote" if os.environ.get("PAPERMATE_API_BASE") else "local",
            samples_dir=os.environ.get("PAPERMATE_SAMPLES_DIR", "data/samples"),
        )
