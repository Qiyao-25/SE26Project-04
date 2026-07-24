"""Deterministic content validation for structured parse outputs (Demo)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FLAG_LABELS: dict[str, str] = {
    "missing_summary": "缺少摘要，需人工复核",
    "missing_concepts": "缺少核心概念",
    "missing_methods": "缺少实现方法",
    "missing_experiments": "缺少实验结果",
    "missing_limitations": "未识别局限性，建议对照原文",
    "missing_source_locator": "缺少原文出处定位",
    "invalid_source_locator": "出处定位无效",
    "experiments_section_not_detected": "未检测到实验相关章节",
    "experiments_content_requires_review": "实验内容不确定，需人工复核",
    "experiments_incomplete": "实验结果不完整",
    "limitations_not_detected": "未检测到局限/讨论章节",
    "limitations_incomplete": "局限性信息不完整",
    "agent_unavailable": "总结 Agent 不可用，使用本地降级结果",
    "low_confidence_summary": "摘要置信度偏低",
    "short_body_excerpt": "正文摘录过短，结构化结果可能不完整",
}


@dataclass(frozen=True)
class ValidationIssue:
    flag: str
    label: str
    severity: str = "warning"  # warning | review | info
    field: str | None = None


@dataclass
class ValidationReport:
    flags: list[str] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    uncertain_fields: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.flags


class ContentValidationAgent:
    """Validate structured wiki fields and mark uncertain sections."""

    def validate_wiki(
        self,
        *,
        summary: str,
        concepts: list[dict[str, Any]] | None = None,
        methods: list[dict[str, Any]] | None = None,
        experiments: list[dict[str, Any]] | None = None,
        limitations: list[str] | None = None,
        page_count: int = 0,
        body_chars: int = 0,
        existing_flags: list[str] | None = None,
        source: str = "",
    ) -> ValidationReport:
        flags: set[str] = {str(item).strip() for item in (existing_flags or []) if str(item).strip()}
        uncertain: set[str] = set()

        if not (summary or "").strip():
            flags.add("missing_summary")
            uncertain.add("summary")
        elif len(summary.strip()) < 40:
            flags.add("low_confidence_summary")
            uncertain.add("summary")

        if not concepts:
            flags.add("missing_concepts")
            uncertain.add("concepts")
        if not methods:
            flags.add("missing_methods")
            uncertain.add("methods")

        experiment_text = " ".join(
            str(item.get("description") or item.get("title") or "")
            for item in (experiments or [])
            if isinstance(item, dict)
        )
        if not experiments:
            flags.add("missing_experiments")
            uncertain.add("experiments")
        elif any(marker in experiment_text for marker in ("需结合", "需要核对", "有限", "不确定", "未明确")):
            flags.add("experiments_content_requires_review")
            uncertain.add("experiments")

        limitation_text = " ".join(str(item) for item in (limitations or []))
        if not limitations:
            flags.add("missing_limitations")
            uncertain.add("limitations")
        elif any(marker in limitation_text for marker in ("未能", "建议人工", "人工复核", "不确定")):
            flags.add("limitations_incomplete")
            uncertain.add("limitations")

        if page_count <= 0 and body_chars < 400:
            flags.add("short_body_excerpt")
            uncertain.update({"summary", "methods", "experiments"})

        if source in {"heuristic_fallback", "abstract_fallback"}:
            flags.add("agent_unavailable")
            uncertain.update({"summary", "concepts", "methods", "experiments", "limitations"})

        if page_count <= 0:
            flags.add("missing_source_locator")

        sorted_flags = sorted(flags)
        issues = [
            ValidationIssue(
                flag=flag,
                label=FLAG_LABELS.get(flag, flag),
                severity=_severity(flag),
                field=_field_for(flag),
            )
            for flag in sorted_flags
        ]
        return ValidationReport(
            flags=sorted_flags,
            issues=issues,
            uncertain_fields=sorted(uncertain),
        )


def flag_labels(flags: list[str]) -> list[str]:
    return [FLAG_LABELS.get(flag, flag) for flag in flags]


def _severity(flag: str) -> str:
    if flag in {"missing_summary", "missing_methods", "invalid_source_locator"}:
        return "review"
    if flag in {"agent_unavailable", "short_body_excerpt"}:
        return "info"
    return "warning"


def _field_for(flag: str) -> str | None:
    mapping = {
        "missing_summary": "summary",
        "low_confidence_summary": "summary",
        "missing_concepts": "concepts",
        "missing_methods": "methods",
        "missing_experiments": "experiments",
        "experiments_content_requires_review": "experiments",
        "experiments_incomplete": "experiments",
        "experiments_section_not_detected": "experiments",
        "missing_limitations": "limitations",
        "limitations_incomplete": "limitations",
        "limitations_not_detected": "limitations",
    }
    return mapping.get(flag)


__all__ = ["ContentValidationAgent", "ValidationReport", "ValidationIssue", "FLAG_LABELS", "flag_labels"]
