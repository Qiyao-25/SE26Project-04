from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class AgentCallError(RuntimeError):
    """Raised when the configured model cannot return a usable response."""


@dataclass(frozen=True)
class AgentConfig:
    enabled: bool = False
    api_key: str = ""
    model: str = ""
    base_url: str = "https://api.openai.com/v1"
    timeout_s: float = 30.0

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            enabled=os.environ.get("PAPERMATE_AGENT_ENABLED", "false").lower() == "true",
            api_key=os.environ.get("PAPERMATE_AGENT_API_KEY", ""),
            model=os.environ.get("PAPERMATE_AGENT_MODEL", ""),
            base_url=os.environ.get("PAPERMATE_AGENT_BASE_URL", "https://api.openai.com/v1"),
            timeout_s=float(os.environ.get("PAPERMATE_AGENT_TIMEOUT_S", "30")),
        )

    @property
    def ready(self) -> bool:
        return self.enabled and bool(self.api_key.strip()) and bool(self.model.strip())


class ChatAgent:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig.from_env()

    @property
    def ready(self) -> bool:
        return self.config.ready

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        if not self.ready:
            raise AgentCallError("agent is disabled or missing api key/model")
        payload = {
            "model": self.config.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "PaperMate-Agent/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise AgentCallError(f"agent request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
            if not isinstance(content, str):
                raise TypeError("message content is not text")
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(content)
            if not isinstance(result, dict):
                raise TypeError("agent JSON is not an object")
            return result
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AgentCallError(f"agent returned invalid JSON: {exc}") from exc
