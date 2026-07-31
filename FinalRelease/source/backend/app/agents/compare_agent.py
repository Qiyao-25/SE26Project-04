"""LLM-backed paper comparison agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings


COMPARE_PROMPT = """你是 PaperMate 的论文对比 Agent。
根据两篇论文的元数据与摘要，生成面向研究者的中文对比总结。
只输出 JSON：
{
  "summary": "2-4 句总体对比概述",
  "similarities": ["相似点1", "相似点2"],
  "differences": ["差异点1", "差异点2"],
  "dimensions": [
    {"aspect": "问题/目标", "paper_a": "当前论文要点", "paper_b": "对比论文要点", "comment": "简短评注"},
    {"aspect": "方法", "paper_a": "...", "paper_b": "...", "comment": "..."},
    {"aspect": "实验/证据", "paper_a": "...", "paper_b": "...", "comment": "..."},
    {"aspect": "贡献与局限", "paper_a": "...", "paper_b": "...", "comment": "..."}
  ],
  "recommendation": "何时优先读哪一篇的一句话建议"
}
规则：
1. 只能依据给定信息，不要编造未出现的数字、数据集或结论。
2. 信息不足时明确写“原文未给出”，不要猜测。
3. similarities / differences 各 2-5 条；dimensions 3-5 项。
4. 不要输出 Markdown 代码块。
"""


@dataclass
class CompareDimension:
    aspect: str
    paper_a: str
    paper_b: str
    comment: str = ""


@dataclass
class CompareResult:
    summary: str
    similarities: list[str] = field(default_factory=list)
    differences: list[str] = field(default_factory=list)
    dimensions: list[CompareDimension] = field(default_factory=list)
    recommendation: str = ""
    source: str = "llm"


class CompareAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def ready(self) -> bool:
        return bool(self.settings.llm_api_key.strip() and self.settings.llm_model.strip())

    def compare(self, *, paper_a: dict[str, Any], paper_b: dict[str, Any]) -> CompareResult:
        if self.ready:
            try:
                return self._compare_with_llm(paper_a=paper_a, paper_b=paper_b)
            except LlmError:
                return self._compare_template(paper_a=paper_a, paper_b=paper_b)
        return self._compare_template(paper_a=paper_a, paper_b=paper_b)

    def _compare_with_llm(self, *, paper_a: dict[str, Any], paper_b: dict[str, Any]) -> CompareResult:
        user = (
            "当前论文（A）：\n"
            f"{_format_paper(paper_a)}\n\n"
            "对比论文（B）：\n"
            f"{_format_paper(paper_b)}\n"
        )
        raw = chat_completion(
            api_key=self.settings.llm_api_key,
            api_base=self.settings.llm_api_base,
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": COMPARE_PROMPT},
                {"role": "user", "content": user},
            ],
            timeout_s=90.0,
            temperature=0.2,
            json_mode=True,
        )
        data = _parse_json(raw)
        summary = str(data.get("summary") or "").strip()
        if not summary:
            return self._compare_template(paper_a=paper_a, paper_b=paper_b)
        dimensions = []
        for item in data.get("dimensions") or []:
            if not isinstance(item, dict):
                continue
            aspect = str(item.get("aspect") or "").strip()
            if not aspect:
                continue
            dimensions.append(
                CompareDimension(
                    aspect=aspect,
                    paper_a=str(item.get("paper_a") or item.get("paperA") or "").strip(),
                    paper_b=str(item.get("paper_b") or item.get("paperB") or "").strip(),
                    comment=str(item.get("comment") or "").strip(),
                )
            )
        return CompareResult(
            summary=summary,
            similarities=_as_str_list(data.get("similarities"))[:6],
            differences=_as_str_list(data.get("differences"))[:6],
            dimensions=dimensions[:6],
            recommendation=str(data.get("recommendation") or "").strip(),
            source="llm",
        )

    def _compare_template(self, *, paper_a: dict[str, Any], paper_b: dict[str, Any]) -> CompareResult:
        title_a = paper_a.get("title") or "当前论文"
        title_b = paper_b.get("title") or "对比论文"
        cat_a = paper_a.get("primary_category") or "未分类"
        cat_b = paper_b.get("primary_category") or "未分类"
        return CompareResult(
            summary=(
                f"《{title_a}》与《{title_b}》可从问题设定、方法路径与证据强度三方面对照阅读。"
                f"当前学科标签分别为 {cat_a} / {cat_b}；以下为基于元数据与摘要的启发式对比，建议结合原文核对。"
            ),
            similarities=[
                "同属学术论文阅读场景，均可从摘要把握问题与贡献",
                "适合并排核对方法主张与实验证据是否充分",
            ],
            differences=[
                f"标题与问题表述不同：A 侧重「{title_a[:48]}」，B 侧重「{title_b[:48]}」",
                f"学科标签不同或表述不同：{cat_a} vs {cat_b}",
            ],
            dimensions=[
                CompareDimension(
                    aspect="问题/目标",
                    paper_a=_clip(paper_a.get("abstract") or paper_a.get("summary") or "原文未给出足够摘要"),
                    paper_b=_clip(paper_b.get("abstract") or paper_b.get("summary") or "原文未给出足够摘要"),
                    comment="优先看摘要首段是否在解决同类问题",
                ),
                CompareDimension(
                    aspect="方法线索",
                    paper_a=_clip(paper_a.get("summary") or paper_a.get("abstract") or "原文未给出"),
                    paper_b=_clip(paper_b.get("summary") or paper_b.get("abstract") or "原文未给出"),
                    comment="信息不足时请打开正文或智能总结核对",
                ),
            ],
            recommendation="若关注方法创新优先精读方法更清晰的一篇；若关注实证效果则优先核对实验与局限更完整的一篇。",
            source="template",
        )


def _format_paper(paper: dict[str, Any]) -> str:
    authors = paper.get("authors") or []
    if isinstance(authors, list):
        authors_text = ", ".join(str(item) for item in authors[:8])
    else:
        authors_text = str(authors)
    return (
        f"标题：{paper.get('title') or '未知'}\n"
        f"作者：{authors_text or '未知'}\n"
        f"学科：{paper.get('primary_category') or '未分类'}\n"
        f"arXiv：{paper.get('arxiv_id') or '无'}\n"
        f"摘要：{_clip(paper.get('abstract') or '', 1200)}\n"
        f"结构化摘要：{_clip(paper.get('summary') or '', 800)}"
    )


def _clip(text: str, limit: int = 280) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return items


def _parse_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmError(f"对比 Agent JSON 解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise LlmError("对比 Agent 未返回对象")
    return data


__all__ = ["CompareAgent", "CompareResult", "CompareDimension"]
