"""QA Agent — 基于论文 chunks 做带出处的智能问答。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings


SYSTEM_PROMPT = """你是 PaperMate 的问答 Agent。
只根据提供的论文证据片段回答用户问题，并标注引用了哪些证据。
必须只输出一个 JSON 对象：
{
  "answer": "面向用户的中文回答",
  "evidence_ids": ["E1", "E2"],
  "refuse": false
}
规则：
1. evidence_ids 只能从给定证据编号中选择（如 E1、E2）；不要编造编号。
2. 每条被引用的证据必须真正支撑 answer 中的对应论断；无关证据不要引用。
3. 证据不足时 refuse=true，evidence_ids 置为空数组，并在 answer 中说明无法核验。
4. 不要编造页码、实验数字或论文未出现的结论。
5. 通常引用 1-3 条最相关证据即可。
"""


@dataclass
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
        evidence_lines = []
        for index, item in enumerate(evidence, start=1):
            eid = f"E{index}"
            id_map[eid] = str(item["chunk_id"])
            id_map[eid.lower()] = str(item["chunk_id"])
            evidence_lines.append(
                f"[{eid}] page={item.get('page_no')} section={item.get('section') or 'body'}\n"
                f"{(item.get('content') or '')[:900]}"
            )

        history_text = ""
        if history:
            clipped = history[-6:]
            history_text = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in clipped)

        user_prompt = (
            f"论文标题: {title}\n"
            f"用户问题: {question}\n"
            f"对话历史:\n{history_text or '(无)'}\n\n"
            f"证据片段:\n" + ("\n\n".join(evidence_lines) if evidence_lines else "(无证据)")
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
            json_mode=True,
            temperature=0.1,
        )
        data = _parse_json_object(raw)
        answer = str(data.get("answer") or "").strip()
        if not answer:
            raise LlmError("问答 Agent 未返回 answer")

        raw_ids = data.get("evidence_ids") or data.get("citation_ids") or []
        citation_ids: list[str] = []
        for cid in raw_ids:
            key = str(cid).strip()
            mapped = id_map.get(key) or id_map.get(key.upper()) or id_map.get(key.lower())
            if mapped and mapped not in citation_ids:
                citation_ids.append(mapped)
        refuse = bool(data.get("refuse"))
        return QaAgentResult(answer=answer, citation_ids=citation_ids, refuse=refuse)


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
