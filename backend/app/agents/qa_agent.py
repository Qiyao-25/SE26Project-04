"""Grounded QA Agent that returns answer text and evidence identifiers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings


SYSTEM_PROMPT = """你是 PaperMate 的论文问答 Agent。
只能根据提供的论文证据片段回答问题，并返回引用了哪些证据。
必须只输出一个 JSON 对象：
{
  "answer": "面向用户的中文回答",
  "evidence_ids": ["E1", "E2"],
  "refuse": false
}
规则：
1. evidence_ids 只能从给定证据编号中选择，不要编造编号。
2. 每条引用证据必须支撑回答中的相关论断。
3. 证据不足时 refuse=true，evidence_ids 返回空数组，并说明无法核验。
4. 不要编造页码、实验数字或论文未出现的结论。
5. 通常引用 1-3 条最相关证据。
6. 对话历史只用于理解追问上下文，不能作为新的事实来源。
7. 如果只能做出推断，必须明确标注“根据证据推测”，不能把推测写成论文结论。
"""


@dataclass(frozen=True)
class QaAgentResult:
    answer: str
    citation_ids: list[str]
    refuse: bool


class QaAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        *,
        title: str,
        question: str,
        evidence: list[dict[str, Any]],
        history: list[dict[str, str]] | None = None,
    ) -> QaAgentResult:
        id_map: dict[str, str] = {}
        evidence_lines: list[str] = []
        for index, item in enumerate(evidence, start=1):
            evidence_id = f"E{index}"
            id_map[evidence_id] = str(item["chunk_id"])
            score = item.get("score")
            score_text = f" retrieval_score={float(score):.3f}" if score is not None else ""
            evidence_lines.append(
                f"[{evidence_id}] page={item.get('page_no')} section={item.get('section') or 'body'}{score_text}\n"
                f"{(item.get('content') or '')[:900]}"
            )

        history_text = "\n".join(
            f"{item.get('role')}: {item.get('content')}"
            for item in (history or [])[-6:]
            if item.get("role") and item.get("content")
        )
        user_prompt = (
            f"论文标题: {title}\n"
            f"用户问题: {question}\n"
            f"对话历史:\n{history_text or '(无)'}\n\n"
            f"证据片段:\n{chr(10).join(evidence_lines) if evidence_lines else '(无证据)'}"
        )
        raw = chat_completion(
            api_key=self.settings.llm_api_key,
            api_base=self.settings.llm_api_base,
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            timeout_s=self.settings.qa_agent_timeout_s,
            temperature=0.1,
            json_mode=True,
        )
        data = _parse_json_object(raw)
        answer = str(data.get("answer") or "").strip()
        if not answer:
            raise LlmError("问答 Agent 未返回 answer")

        raw_ids = data.get("evidence_ids") or data.get("citation_ids") or []
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]
        if not isinstance(raw_ids, list):
            raise LlmError("问答 Agent evidence_ids 格式异常")
        citation_ids: list[str] = []
        for raw_id in raw_ids:
            evidence_id = str(raw_id).strip().upper()
            chunk_id = id_map.get(evidence_id)
            if chunk_id and chunk_id not in citation_ids:
                citation_ids.append(chunk_id)
        return QaAgentResult(answer=answer, citation_ids=citation_ids, refuse=_as_bool(data.get("refuse")))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes", "是"}
    return bool(value)


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmError(f"问答 Agent 输出不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LlmError("问答 Agent JSON 根节点必须是对象")
    return data


__all__ = ["QaAgent", "QaAgentResult"]
