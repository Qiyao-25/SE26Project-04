"""Search Agent - natural language query rewrite + search answer generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings
from app.service.qa_citations import expand_query_tokens


REWRITE_PROMPT = """你是 PaperMate 的论文检索 Agent。
把用户的自然语言检索意图改写成便于数据库模糊匹配的关键词。
只输出 JSON：
{
  "rewritten_query": "简短检索短语（可中英混合）",
  "keywords": ["关键词1", "keyword2"],
  "category_hints": ["cs.CL"],
  "intent": "一句话说明用户想找什么"
}
规则：
1. keywords 3-8 个，包含中英文同义表达（如 注意力/attention、Transformer）。
2. 不要编造具体 arXiv ID，除非用户明确给出。
3. category_hints 可选，使用 arXiv 分类如 cs.CL、cs.LG、cs.CV。
4. 若用户输入看起来像完整论文标题，rewritten_query 应尽量保留原标题用语，keywords 以标题核心词为主，category_hints 可为空。
5. 同一意图应输出稳定、可复现的 keywords（按重要性排序），不要随意换词。
"""


ANSWER_PROMPT = """你是 PaperMate 的论文检索助手。
根据用户问题与检索到的论文列表，生成简短中文回复（2-5 句）。
只输出 JSON：
{
  "answer": "面向用户的回答，可概括匹配理由并点名 1-3 篇标题",
  "highlights": ["可选：匹配要点"]
}
规则：
1. 只依据给定论文列表，不要捏造未出现的论文。
2. 若列表为空，礼貌建议换更短的英文关键词或研究方向。
3. 不要输出 Markdown 代码块。
"""


@dataclass
class SearchPlan:
    rewritten_query: str
    keywords: list[str] = field(default_factory=list)
    category_hints: list[str] = field(default_factory=list)
    intent: str = ""
    source: str = "heuristic"


@dataclass
class SearchAnswer:
    answer: str
    highlights: list[str] = field(default_factory=list)
    source: str = "template"


class SearchAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def ready(self) -> bool:
        return bool(getattr(self.settings, "search_agent_enabled", True) and self.settings.llm_api_key.strip())

    def plan(self, query: str) -> SearchPlan:
        query = (query or "").strip()
        if not query:
            return SearchPlan(rewritten_query="", keywords=[], intent="")

        if self.ready:
            try:
                return self._plan_with_llm(query)
            except LlmError:
                pass
        return self._plan_heuristic(query)

    def answer(self, *, query: str, plan: SearchPlan, papers: list[dict[str, Any]], total: int) -> SearchAnswer:
        if self.ready and papers is not None:
            try:
                return self._answer_with_llm(query=query, plan=plan, papers=papers, total=total)
            except LlmError:
                pass
        return self._answer_template(query=query, plan=plan, papers=papers, total=total)

    def _plan_with_llm(self, query: str) -> SearchPlan:
        raw = chat_completion(
            api_key=self.settings.llm_api_key,
            api_base=self.settings.llm_api_base,
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": REWRITE_PROMPT},
                {"role": "user", "content": f"用户检索：{query}"},
            ],
            timeout_s=getattr(self.settings, "search_agent_timeout_s", 45.0),
            json_mode=True,
            temperature=0.0,
        )
        data = _parse_json(raw)
        keywords = _as_str_list(data.get("keywords"))
        rewritten = str(data.get("rewritten_query") or query).strip() or query
        if not keywords:
            keywords = _heuristic_keywords(query)
        for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}|[\u4e00-\u9fff]{2,}", rewritten):
            if token not in keywords:
                keywords.append(token)
        return SearchPlan(
            rewritten_query=rewritten,
            keywords=_dedupe(keywords)[:10],
            category_hints=_as_str_list(data.get("category_hints"))[:5],
            intent=str(data.get("intent") or "").strip(),
            source="llm",
        )

    def _plan_heuristic(self, query: str) -> SearchPlan:
        return SearchPlan(
            rewritten_query=query,
            keywords=_heuristic_keywords(query),
            category_hints=[],
            intent="基于关键词的模糊匹配",
            source="heuristic",
        )

    def _answer_with_llm(self, *, query: str, plan: SearchPlan, papers: list[dict[str, Any]], total: int) -> SearchAnswer:
        lines = []
        for index, paper in enumerate(papers[:8], start=1):
            lines.append(
                f"{index}. {paper.get('title')} | authors={', '.join(paper.get('authors') or [])} | "
                f"cat={paper.get('primary_category')} | abstract={(paper.get('abstract') or '')[:180]}"
            )
        user_prompt = (
            f"用户问题：{query}\n"
            f"检索意图：{plan.intent or plan.rewritten_query}\n"
            f"关键词：{', '.join(plan.keywords)}\n"
            f"命中总数：{total}\n"
            f"论文列表：\n" + ("\n".join(lines) if lines else "(无)")
        )
        raw = chat_completion(
            api_key=self.settings.llm_api_key,
            api_base=self.settings.llm_api_base,
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": ANSWER_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            timeout_s=getattr(self.settings, "search_agent_timeout_s", 45.0),
            json_mode=True,
            temperature=0.0,
        )
        data = _parse_json(raw)
        answer = str(data.get("answer") or "").strip()
        if not answer:
            return self._answer_template(query=query, plan=plan, papers=papers, total=total)
        return SearchAnswer(answer=answer, highlights=_as_str_list(data.get("highlights"))[:5], source="llm")

    def _answer_template(self, *, query: str, plan: SearchPlan, papers: list[dict[str, Any]], total: int) -> SearchAnswer:
        if total <= 0:
            return SearchAnswer(
                answer=f"未找到与“{query}”匹配的论文。可尝试更短的英文关键词（如 attention、transformer），或更换研究方向。",
                source="template",
            )
        titles = [str(p.get("title") or "") for p in papers[:3] if p.get("title")]
        named = "、".join(f"《{title}》" for title in titles)
        keywords = "、".join(plan.keywords[:5]) or query
        answer = f"已根据“{keywords}”完成智能匹配，共找到 {total} 篇相关论文。"
        if named:
            answer += f" 其中较相关的包括：{named}。"
        if plan.intent:
            answer += f" 检索意图：{plan.intent}"
        return SearchAnswer(answer=answer, highlights=plan.keywords[:5], source="template")


def _heuristic_keywords(query: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}|[\u4e00-\u9fff]{2,}", query or "")
    expanded = list(expand_query_tokens(query))
    merged = _dedupe(tokens + [token for token in expanded if re.search(r"[A-Za-z]", token) or len(token) >= 2])
    if query.strip() and query.strip() not in merged:
        merged.insert(0, query.strip())
    return merged[:10]


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := str(item or "").strip())]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise LlmError("Search Agent JSON 根节点必须是对象")
    return data


__all__ = ["SearchAgent", "SearchPlan", "SearchAnswer"]
