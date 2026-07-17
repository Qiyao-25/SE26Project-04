from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings


class AgentCallError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentAnswer:
    answer: str
    citation_ids: list[str]


class AgentClient:
    def __init__(self, settings: Settings):
        self.enabled = settings.agent_enabled and bool(settings.agent_api_key) and bool(settings.agent_model)
        self.api_key = settings.agent_api_key or ""
        self.model = settings.agent_model
        self.base_url = settings.agent_base_url.rstrip("/")
        self.timeout_s = settings.agent_timeout_s

    def answer(self, *, question: str, evidence: list[dict[str, Any]], history: list[dict[str, str]] | None = None) -> str:
        if not self.enabled:
            raise AgentCallError("agent is disabled or missing api key/model")
        evidence_text = "\n\n".join(
            f"[{item.get('chunk_id')} page={item.get('page_no')} section={item.get('section')}] {item.get('content', '')}"
            for item in evidence
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a grounded research assistant. Answer only from the supplied evidence. "
                    "If the evidence is insufficient, say so. Return JSON with one key: answer. "
                    "Do not create citations or facts that are not present in the evidence."
                ),
            }
        ]
        for item in (history or [])[-6:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append({"role": item["role"], "content": item["content"]})
        messages.append(
            {
                "role": "user",
                "content": f"Question: {question}\n\nEvidence:\n{evidence_text}",
            }
        )
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "PaperMate-QA-Agent/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise AgentCallError(f"agent request failed: {exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
            result = json.loads(str(content).strip().strip("`").replace("json\n", "", 1))
            answer = str(result.get("answer") or "").strip()
            if not answer:
                raise ValueError("empty answer")
            citation_ids = result.get("citation_ids")
            if isinstance(citation_ids, str):
                citation_ids = [citation_ids]
            if not isinstance(citation_ids, list):
                raise ValueError("citation_ids must be a list")
            return AgentAnswer(
                answer=answer,
                citation_ids=list(dict.fromkeys(str(item).strip() for item in citation_ids if str(item).strip())),
            )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AgentCallError(f"agent returned invalid answer: {exc}") from exc
