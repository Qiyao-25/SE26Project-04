"""Deterministic LLM substitute used by Harness scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HarnessLlmStub:
    """Return contract-valid responses without making a network request."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(
        self,
        *,
        api_key: str,
        api_base: str,
        model: str,
        messages: list[dict[str, str]],
        timeout_s: float,
        temperature: float,
        json_mode: bool,
    ) -> str:
        del api_key, api_base, model, timeout_s, temperature, json_mode
        system = messages[0].get("content", "") if messages else ""
        user = messages[-1].get("content", "") if messages else ""
        self.calls.append({"system": system, "user": user})

        if "论文阅读 Agent" in system:
            return json.dumps(
                {
                    "summary": "该论文提出一种基于 self-attention 的序列建模方法，并通过实验验证其效果。",
                    "concepts": [
                        {
                            "name": "Self-Attention",
                            "description": "利用序列内部的注意力关系建模不同位置之间的依赖。",
                        }
                    ],
                    "methods": [
                        {
                            "title": "Self-Attention Architecture",
                            "description": "使用多头 self-attention 和前馈网络组成编码与解码模块。",
                        }
                    ],
                    "experiments": [
                        {
                            "title": "Benchmark Evaluation",
                            "description": "在 benchmark translation tasks 上评估模型性能。",
                        }
                    ],
                    "limitations": ["需要结合论文原文进一步核对适用范围。"],
                    "validation_flags": [],
                },
                ensure_ascii=False,
            )

        if "论文问答检索规划 Agent" in system:
            return json.dumps(
                {
                    "paper_related": True,
                    "search_queries": ["self-attention architecture", "benchmark evaluation"],
                },
                ensure_ascii=False,
            )

        if "论文问答 Agent" in system:
            return json.dumps(
                {
                    "answer": "论文提出了基于 self-attention 的架构，用于建模序列中不同位置之间的依赖。",
                    "evidence_ids": ["E1"],
                    "refuse": False,
                },
                ensure_ascii=False,
            )

        raise AssertionError(f"Harness LLM stub received an unsupported prompt: {system[:80]}")


__all__ = ["HarnessLlmStub"]
