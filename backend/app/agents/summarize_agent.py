"""LLM-backed structured summary Agent used by backend parse integrations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings


SYSTEM_PROMPT = """你是 PaperMate 的论文阅读 Agent。
根据标题、摘要和正文片段生成结构化论文知识，只输出 JSON：
{
  "summary": "中文结构化摘要",
  "concepts": [{"name": "概念", "description": "解释"}],
  "methods": [{"title": "步骤", "description": "说明"}],
  "experiments": [{"title": "实验", "description": "结果"}],
  "limitations": ["局限"],
  "validation_flags": ["风险标记"]
}
只能依据输入内容，不要编造论文未出现的数字或结论。
"""


@dataclass
class AgentWiki:
    summary: str
    concepts: list[dict[str, Any]]
    methods: list[dict[str, Any]]
    experiments: list[dict[str, Any]]
    limitations: list[str]
    validation_flags: list[str]
    source: str = "llm_summarize_agent"

    def to_structured_rows(self, *, page_count: int = 0) -> list[dict[str, Any]]:
        locator = {"page_count": page_count, "source": self.source}
        return [
            {"result_type": "summary", "version": 1, "content_json": {"summary": self.summary}, "source_locator": locator, "confidence": 0.8},
            {"result_type": "concepts", "version": 1, "content_json": {"items": self.concepts}, "source_locator": locator, "confidence": 0.75},
            {"result_type": "methods", "version": 1, "content_json": {"items": self.methods}, "source_locator": locator, "confidence": 0.75},
            {"result_type": "experiments", "version": 1, "content_json": {"items": self.experiments}, "source_locator": locator, "confidence": 0.7},
            {"result_type": "limitations", "version": 1, "content_json": {"items": self.limitations}, "source_locator": locator, "confidence": 0.7},
            {"result_type": "validation", "version": 1, "content_json": {"flags": self.validation_flags}, "source_locator": locator, "confidence": 1.0},
        ]


class SummarizeAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, *, title: str, abstract: str, body_text: str, arxiv_id: str = "") -> AgentWiki:
        raw = chat_completion(
            api_key=self.settings.llm_api_key,
            api_base=self.settings.llm_api_base,
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"arxiv_id: {arxiv_id}\ntitle: {title}\nabstract: {abstract or '(无)'}\nbody_excerpt:\n{(body_text or '')[:12000] or '(无正文)'}"},
            ],
            timeout_s=self.settings.parse_agent_timeout_s,
            json_mode=True,
        )
        return _normalize(json.loads(_strip_fence(raw)), arxiv_id or "paper")


def build_fallback_summary(*, title: str, abstract: str, body_text: str, arxiv_id: str = "") -> AgentWiki:
    """Build a usable deterministic result when the remote model is unavailable."""
    text = re.sub(r"\s+", " ", (body_text or abstract or "")).strip()
    abstract_text = re.sub(r"\s+", " ", (abstract or "")).strip()
    sentences = [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+", text) if item.strip()]
    summary = (abstract_text or " ".join(sentences[:3]) or title or "论文正文已解析").strip()[:1600]

    method_sentences = [
        item for item in sentences
        if any(keyword in item.casefold() for keyword in ("method", "approach", "model", "architecture", "attention", "方法", "模型"))
    ][:3]
    experiment_sentences = [
        item for item in sentences
        if any(keyword in item.casefold() for keyword in ("experiment", "result", "evaluation", "benchmark", "bleu", "accuracy", "实验", "结果"))
    ][:3]
    method_text = " ".join(method_sentences)[:1200] or summary[:600]
    experiment_text = " ".join(experiment_sentences)[:1200] or "已完成正文解析；实验细节需要结合原文核对。"
    concept_name = title[:80] if title else "论文核心方法"
    return AgentWiki(
        summary=summary,
        concepts=[{"conceptId": f"{arxiv_id or 'paper'}-concept-1", "name": concept_name, "description": summary[:500]}],
        methods=[{"order": 1, "title": "方法概览", "description": method_text}],
        experiments=[{"title": "实验与结果", "description": experiment_text}],
        limitations=["未调用远程总结 Agent，局限性需要人工复核。"],
        validation_flags=["agent_unavailable"],
        source="heuristic_fallback",
    )


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _normalize(data: dict[str, Any], paper_id: str) -> AgentWiki:
    if not isinstance(data, dict):
        raise LlmError("Summarize Agent JSON 根节点必须是对象")
    summary = str(data.get("summary") or "").strip()
    if not summary:
        raise LlmError("Summarize Agent 未返回 summary")

    concepts = []
    for index, item in enumerate(data.get("concepts") or [], 1):
        if isinstance(item, str) and item.strip():
            concepts.append({"conceptId": f"{paper_id}-concept-{index}", "name": item.strip()[:80], "description": item.strip()})
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or "").strip()
            if name:
                concepts.append({"conceptId": str(item.get("conceptId") or f"{paper_id}-concept-{index}"), "name": name[:80], "description": str(item.get("description") or item.get("desc") or name).strip()})

    def normalize_steps(values: Any) -> list[dict[str, Any]]:
        output = []
        for index, item in enumerate(values or [], 1):
            if isinstance(item, str) and item.strip():
                output.append({"order": index, "title": f"步骤 {index}", "description": item.strip()})
            elif isinstance(item, dict):
                title = str(item.get("title") or item.get("name") or f"步骤 {index}").strip()
                description = str(item.get("description") or item.get("desc") or "").strip()
                if title or description:
                    output.append({"order": int(item.get("order") or index), "title": title, "description": description})
        return output

    methods = normalize_steps(data.get("methods"))
    experiments = [{"title": str(item.get("title") or item.get("name") or "实验"), "description": str(item.get("description") or item.get("desc") or "").strip()} for item in (data.get("experiments") or []) if isinstance(item, dict)]
    limitations = [str(item.get("description") or item.get("text") or item.get("name") or "").strip() if isinstance(item, dict) else str(item).strip() for item in (data.get("limitations") or [])]
    limitations = [item for item in limitations if item]
    flags = [str(item).strip() for item in (data.get("validation_flags") or []) if str(item).strip()]
    if not concepts:
        concepts = [{"conceptId": f"{paper_id}-concept-1", "name": "核心贡献", "description": summary[:300]}]
    if not methods:
        methods = [{"order": 1, "title": "方法概述", "description": summary[:400]}]
    if not experiments:
        experiments = [{"title": "实验与结果", "description": "原文实验细节有限，需结合 PDF 核对。"}]
        flags.append("experiments_incomplete")
    if not limitations:
        limitations = ["Agent 未能从摘录中明确识别局限性，建议人工复核。"]
        flags.append("limitations_incomplete")
    return AgentWiki(summary, concepts, methods, experiments, limitations, sorted(set(flags)))


__all__ = ["AgentWiki", "SummarizeAgent", "build_fallback_summary"]
