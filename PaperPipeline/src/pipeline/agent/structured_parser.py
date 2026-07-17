from __future__ import annotations

from typing import Any

from ..parser.pdf_parse import Paragraph
from ..summarizer.struct_summary import StructuredWiki
from ..validation import ContentValidationAgent
from .client import AgentCallError, ChatAgent


def _evidence(paragraphs: list[Paragraph], max_chars: int = 60000) -> str:
    parts: list[str] = []
    used = 0
    for paragraph in paragraphs:
        item = f"[{paragraph.para_id} page={paragraph.page} section={paragraph.section}] {paragraph.text}"
        if used + len(item) > max_chars:
            break
        parts.append(item)
        used += len(item) + 2
    return "\n\n".join(parts)


def _string_list(value: Any) -> list[str]:
    """Normalize provider output that may use a string instead of an array."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def build_structured_with_agent(
    arxiv_id: str,
    paragraphs: list[Paragraph],
    *,
    title: str = "",
    abstract_hint: str = "",
    agent: ChatAgent | None = None,
) -> StructuredWiki:
    agent = agent or ChatAgent()
    result = agent.complete_json(
        system=(
            "You are a paper understanding agent. Use only the supplied paper evidence. "
            "Return JSON with exactly these keys: summary, concept, methods, experiments, "
            "limitations, source_para_ids. summary/concept/methods/experiments are strings; "
            "limitations/source_para_ids are arrays of strings. Every source_para_id must "
            "match an evidence paragraph ID. Do not invent facts or citations."
        ),
        user=(
            f"Paper title: {title}\n"
            f"arXiv ID: {arxiv_id}\n"
            f"Metadata abstract: {abstract_hint}\n\n"
            f"Evidence:\n{_evidence(paragraphs)}"
        ),
    )
    paragraph_ids = {paragraph.para_id for paragraph in paragraphs}
    source_ids = [item for item in _string_list(result.get("source_para_ids")) if item in paragraph_ids]
    summary = str(result.get("summary") or "").strip()
    concept = str(result.get("concept") or "").strip()
    methods = str(result.get("methods") or "").strip()
    experiments = str(result.get("experiments") or "").strip()
    limitations = _string_list(result.get("limitations"))
    flags = ContentValidationAgent().validate(
        summary=summary,
        concept=concept,
        methods=methods,
        experiments=experiments,
        source_para_ids=source_ids,
        paragraphs=paragraphs,
    ).flags
    return StructuredWiki(
        arxiv_id=arxiv_id,
        summary=summary,
        concept=concept,
        methods=methods,
        experiments=experiments,
        limitations=limitations,
        ok=bool(summary and concept and methods and experiments),
        source_para_ids=source_ids,
        validation_flags=flags,
    )


__all__ = ["AgentCallError", "build_structured_with_agent"]
