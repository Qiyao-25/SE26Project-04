"""Summarize Agent — DeepSeek 生成论文结构化 Wiki（summary/concepts/methods/...）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.agents.deepseek_client import DeepSeekError, chat_completion
from app.core.config import Settings


SYSTEM_PROMPT = """你是 PaperMate 的论文阅读 Agent（Summarize Agent）。
根据给定论文标题、摘要与正文片段，生成结构化知识，供前端「智能总结」页展示。
必须只输出一个 JSON 对象，字段如下：
{
  "summary": "中文结构化摘要，200-400字",
  "concepts": [{"name": "概念名", "description": "解释"}],
  "methods": [{"title": "步骤标题", "description": "说明"}],
  "experiments": [{"title": "实验名", "description": "结果与指标"}],
  "limitations": ["局限1", "局限2"],
  "validation_flags": ["可选风险标记，如 uncertain_claim"]
}
要求：
1. 忠实于原文，不要编造未出现的数据；不确定处在 validation_flags 中标记。
2. concepts 3-6 条；methods 3-5 步；experiments 1-4 条；limitations 1-4 条。
3. 全部使用简体中文。
"""


@dataclass
class AgentWiki:
    summary: str
    concepts: list[dict[str, Any]]
    methods: list[dict[str, Any]]
    experiments: list[dict[str, Any]]
    limitations: list[str]
    validation_flags: list[str]
    source: str = "deepseek_summarize_agent"

    def to_structured_rows(self, *, page_count: int = 0) -> list[dict[str, Any]]:
        locator = {"page_count": page_count, "source": self.source}
        return [
            {
                "result_type": "summary",
                "version": 1,
                "content_json": {"summary": self.summary},
                "source_locator": locator,
                "confidence": 0.8,
            },
            {
                "result_type": "concepts",
                "version": 1,
                "content_json": {"items": self.concepts},
                "source_locator": locator,
                "confidence": 0.75,
            },
            {
                "result_type": "methods",
                "version": 1,
                "content_json": {"items": self.methods},
                "source_locator": locator,
                "confidence": 0.75,
            },
            {
                "result_type": "experiments",
                "version": 1,
                "content_json": {"items": self.experiments},
                "source_locator": locator,
                "confidence": 0.7,
            },
            {
                "result_type": "limitations",
                "version": 1,
                "content_json": {"items": self.limitations},
                "source_locator": locator,
                "confidence": 0.7,
            },
            {
                "result_type": "validation",
                "version": 1,
                "content_json": {"flags": self.validation_flags},
                "source_locator": locator,
                "confidence": 1.0,
            },
        ]


class SummarizeAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        *,
        title: str,
        abstract: str,
        body_text: str,
        arxiv_id: str = "",
    ) -> AgentWiki:
        clipped = (body_text or "")[:12000]
        user_prompt = (
            f"arxiv_id: {arxiv_id}\n"
            f"title: {title}\n"
            f"abstract: {abstract or '(无)'}\n"
            f"body_excerpt:\n{clipped or '(无正文，请主要依据标题与摘要)'}\n"
        )
        raw = chat_completion(
            api_key=self.settings.deepseek_api_key,
            api_base=self.settings.deepseek_api_base,
            model=self.settings.deepseek_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            timeout_s=self.settings.parse_agent_timeout_s,
        )
        data = _parse_json_object(raw)
        return _normalize_wiki(data, paper_id_hint=arxiv_id or "paper")


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DeepSeekError(f"Agent 输出不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DeepSeekError("Agent JSON 根节点必须是对象")
    return data


def _normalize_wiki(data: dict[str, Any], *, paper_id_hint: str) -> AgentWiki:
    summary = str(data.get("summary") or "").strip()
    if not summary:
        raise DeepSeekError("Agent 未返回 summary")

    concepts: list[dict[str, Any]] = []
    for index, item in enumerate(data.get("concepts") or []):
        if isinstance(item, str) and item.strip():
            concepts.append(
                {
                    "conceptId": f"{paper_id_hint}-concept-{index + 1}",
                    "name": item.strip()[:80],
                    "description": item.strip(),
                }
            )
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or "").strip()
            desc = str(item.get("description") or item.get("desc") or name).strip()
            if name:
                concepts.append(
                    {
                        "conceptId": str(item.get("conceptId") or f"{paper_id_hint}-concept-{index + 1}"),
                        "name": name[:80],
                        "description": desc,
                    }
                )

    methods: list[dict[str, Any]] = []
    for index, item in enumerate(data.get("methods") or []):
        if isinstance(item, str) and item.strip():
            methods.append({"order": index + 1, "title": f"步骤 {index + 1}", "description": item.strip()})
        elif isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or f"步骤 {index + 1}").strip()
            desc = str(item.get("description") or item.get("desc") or "").strip()
            if title or desc:
                methods.append({"order": int(item.get("order") or index + 1), "title": title, "description": desc})

    experiments: list[dict[str, Any]] = []
    for item in data.get("experiments") or []:
        if isinstance(item, str) and item.strip():
            experiments.append({"title": "实验结果", "description": item.strip()})
        elif isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or "实验").strip()
            desc = str(item.get("description") or item.get("desc") or "").strip()
            if title or desc:
                experiments.append({"title": title, "description": desc})

    limitations: list[str] = []
    for item in data.get("limitations") or []:
        if isinstance(item, str) and item.strip():
            limitations.append(item.strip())
        elif isinstance(item, dict):
            text = str(item.get("description") or item.get("text") or item.get("name") or "").strip()
            if text:
                limitations.append(text)

    flags = [str(f).strip() for f in (data.get("validation_flags") or []) if str(f).strip()]
    flags.append("generated_by_summarize_agent")

    if not concepts:
        concepts = [
            {
                "conceptId": f"{paper_id_hint}-concept-1",
                "name": "核心贡献",
                "description": summary[:300],
            }
        ]
    if not methods:
        methods = [{"order": 1, "title": "方法概述", "description": summary[:400]}]
    if not experiments:
        experiments = [{"title": "实验与结果", "description": "原文实验细节有限，需结合 PDF 核对。"}]
        flags.append("experiments_incomplete")
    if not limitations:
        limitations = ["Agent 未能从摘录中明确识别局限性，建议人工复核。"]
        flags.append("limitations_incomplete")

    return AgentWiki(
        summary=summary,
        concepts=concepts,
        methods=methods,
        experiments=experiments,
        limitations=limitations,
        validation_flags=sorted(set(flags)),
    )


__all__ = ["SummarizeAgent", "AgentWiki"]
