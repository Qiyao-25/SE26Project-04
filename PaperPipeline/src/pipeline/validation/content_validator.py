"""Deterministic content validation for extracted structured results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ValidationReport:
    flags: list[str]

    @property
    def passed(self) -> bool:
        return not self.flags


class ContentValidationAgent:
    """Validate evidence links and required structured output fields.

    This is intentionally deterministic for the technical demo. A future LLM
    validator can keep this contract and add semantic checks behind it.
    """

    def validate(
        self,
        *,
        summary: str,
        concept: str,
        methods: str,
        experiments: str,
        source_para_ids: list[str],
        paragraphs: Sequence[object],
    ) -> ValidationReport:
        flags: list[str] = []
        required = {
            "summary": summary,
            "concept": concept,
            "methods": methods,
            "experiments": experiments,
        }
        flags.extend(f"missing_{name}" for name, value in required.items() if not value.strip())

        paragraph_ids = {getattr(paragraph, "para_id", "") for paragraph in paragraphs}
        if not source_para_ids:
            flags.append("missing_source_locator")
        elif any(source_id not in paragraph_ids for source_id in source_para_ids):
            flags.append("invalid_source_locator")

        sections = {getattr(paragraph, "section", "") for paragraph in paragraphs}
        if not sections.intersection({"experiment", "experiments", "results", "evaluation"}):
            flags.append("experiments_section_not_detected")
        if "未从解析文本中识别" in experiments:
            flags.append("experiments_content_requires_review")
        if not sections.intersection({"discussion", "conclusion", "limitations"}):
            flags.append("limitations_not_detected")
        return ValidationReport(flags=sorted(set(flags)))


__all__ = ["ContentValidationAgent", "ValidationReport"]
