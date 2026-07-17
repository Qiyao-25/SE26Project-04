"""Minimal OpenAI-compatible DeepSeek chat client (stdlib only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class DeepSeekError(RuntimeError):
    pass


def chat_completion(
    *,
    api_key: str,
    api_base: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_s: float = 90.0,
    temperature: float = 0.2,
) -> str:
    if not api_key.strip():
        raise DeepSeekError("DeepSeek API key 未配置（PAPERMATE_DEEPSEEK_API_KEY）")

    url = f"{api_base.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
            "User-Agent": "PaperMate-Backend-Agent/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise DeepSeekError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise DeepSeekError(f"DeepSeek 调用失败: {exc}") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError(f"DeepSeek 响应格式异常: {payload!r}") from exc
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekError("DeepSeek 返回空内容")
    return content
