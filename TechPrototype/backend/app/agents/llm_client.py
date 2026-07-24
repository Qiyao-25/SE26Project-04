"""Small provider-agnostic OpenAI-compatible chat client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class LlmError(RuntimeError):
    """Raised when the configured LLM cannot return a usable response."""


def chat_completion(
    *,
    api_key: str,
    api_base: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_s: float = 90.0,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    if not api_key.strip():
        raise LlmError("LLM API key 未配置")
    if not model.strip():
        raise LlmError("LLM model 未配置")

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
            "User-Agent": "PaperMate-Backend-Agent/0.2",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise LlmError(f"LLM HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise LlmError(f"LLM 调用失败: {exc}") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("LLM 响应格式异常") from exc
    if isinstance(content, list):
        content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
    if not isinstance(content, str) or not content.strip():
        raise LlmError("LLM 返回空内容")
    return content


__all__ = ["LlmError", "chat_completion"]
