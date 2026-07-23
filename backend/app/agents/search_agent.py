"""Search Agent - natural language query rewrite + search answer generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings
from app.service.qa_citations import expand_query_tokens
from app.service.search_query_normalize import (
    expand_chinese_topics,
    extract_arxiv_id,
    extract_author_candidates,
    infer_search_mode,
    romanize_chinese_person_name,
    strip_query_fillers,
)


REWRITE_PROMPT = """你是 PaperMate 的论文检索 Agent。
把用户的自然语言检索意图改写成便于数据库模糊匹配的结构化计划。
数据库作者字段多为英文（如 Beijun Shen），标题/摘要多为英文，主题分类为 arXiv 代码（如 cs.SE）。

只输出 JSON：
{
  "rewritten_query": "简短检索短语（优先英文，可中英混合）",
  "keywords": ["keyword1", "keyword2"],
  "author_hints": ["Beijun Shen"],
  "category_hints": ["cs.CL"],
  "search_mode": "topic|author|mixed|arxiv|title",
  "intent": "一句话说明用户想找什么"
}

规则：
1. 口语填充词（找一下/帮我搜/有没有/请）不要进入 keywords。
2. 汉语人名必须识别并罗马化为学术英文作者格式：名在前姓在后，如「沈备军」→「Beijun Shen」。
   author_hints 至少包含：Given Family、可选 Family Given、可选姓氏。不要保留「老师/教授」等称谓。
3. 若用户在找某人的论文（如「沈备军老师的论文」「papers by X」），search_mode=author，keywords 以作者英文为主，不要塞无关主题词。
4. 若同时有作者与主题（如「沈备军关于代码生成的论文」），search_mode=mixed，author_hints 放作者，keywords 放主题英文词。
5. 中文研究方向要改写成常用英文检索词（代码生成→code generation；自然语言处理→NLP / natural language processing）。
6. keywords 2-5 个，只保留高区分度词；禁止 paper/method/model/learning/study/研究/方法/模型/论文 等泛化词。
7. 不要编造 arXiv ID；用户给出编号时 search_mode=arxiv，keywords 放该编号。
8. 完整论文标题检索：search_mode=title，尽量保留原标题用语。
9. category_hints 可选且宜少；不确定则 []。
10. 同一意图输出稳定可复现的 keywords / author_hints（按重要性排序）。
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
2. 若是按作者检索，说明是否命中该作者（用英文作者名对照列表），不要编造作者关系。
3. 若列表为空，礼貌建议：作者可试英文名（名在前姓在后）、主题可试更短英文关键词。
4. 不要输出 Markdown 代码块，不要输出「出处」或空引用。
"""


@dataclass
class SearchPlan:
    rewritten_query: str
    keywords: list[str] = field(default_factory=list)
    author_hints: list[str] = field(default_factory=list)
    category_hints: list[str] = field(default_factory=list)
    search_mode: str = "topic"
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

        heuristic = self._plan_heuristic(query)
        if self.ready:
            try:
                llm_plan = self._plan_with_llm(query)
                return _merge_plans(heuristic, llm_plan)
            except LlmError:
                pass
        return heuristic

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
        author_hints = _as_str_list(data.get("author_hints"))
        rewritten = str(data.get("rewritten_query") or query).strip() or query
        mode = str(data.get("search_mode") or "").strip().lower()
        if mode not in {"topic", "author", "mixed", "arxiv", "title"}:
            mode = infer_search_mode(query, author_hints=author_hints)
        if not keywords:
            keywords = _heuristic_keywords(query)
        # Ensure Chinese names in author_hints get English variants.
        expanded_authors: list[str] = []
        for hint in author_hints:
            expanded_authors.extend(romanize_chinese_person_name(hint) or [hint])
        return SearchPlan(
            rewritten_query=rewritten,
            keywords=_dedupe(keywords)[:5],
            author_hints=_dedupe(expanded_authors)[:6],
            category_hints=_as_str_list(data.get("category_hints"))[:3],
            search_mode=mode,
            intent=str(data.get("intent") or "").strip(),
            source="llm",
        )

    def _plan_heuristic(self, query: str) -> SearchPlan:
        arxiv_id = extract_arxiv_id(query)
        authors = extract_author_candidates(query)
        topic_kw, categories = expand_chinese_topics(query)
        mode = infer_search_mode(query, author_hints=authors)
        cleaned = strip_query_fillers(query)

        if arxiv_id:
            return SearchPlan(
                rewritten_query=arxiv_id,
                keywords=[arxiv_id],
                author_hints=[],
                category_hints=[],
                search_mode="arxiv",
                intent=f"按 arXiv 编号检索 {arxiv_id}",
                source="heuristic",
            )

        keywords: list[str] = []
        if mode in {"author", "mixed"} and authors:
            keywords.extend(authors[:3])
        keywords.extend(topic_kw)
        if mode == "topic":
            keywords.extend(_heuristic_keywords(cleaned))
        elif mode == "mixed":
            keywords.extend(_heuristic_keywords(cleaned))
        keywords = _dedupe([k for k in keywords if k.casefold() not in _HEURISTIC_STOP])[:5]

        rewritten = authors[0] if mode == "author" and authors else (topic_kw[0] if topic_kw else cleaned)
        if mode == "mixed" and authors and topic_kw:
            rewritten = f"{authors[0]} {topic_kw[0]}"
        intent = {
            "author": f"按作者检索：{authors[0] if authors else cleaned}",
            "mixed": f"按作者与主题检索：{rewritten}",
            "topic": "基于关键词的模糊匹配",
        }.get(mode, "基于关键词的模糊匹配")

        return SearchPlan(
            rewritten_query=rewritten,
            keywords=keywords or _heuristic_keywords(cleaned) or [cleaned],
            author_hints=authors[:6],
            category_hints=categories[:3],
            search_mode=mode,
            intent=intent,
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
            f"检索模式：{plan.search_mode}\n"
            f"作者提示：{', '.join(plan.author_hints) or '无'}\n"
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
            hint = ""
            if plan.author_hints:
                hint = f" 可尝试英文作者名「{plan.author_hints[0]}」。"
            return SearchAnswer(
                answer=f"未找到与“{query}”匹配的论文。{hint}也可尝试更短的英文主题词或更换研究方向。".strip(),
                source="template",
            )
        titles = [str(p.get("title") or "") for p in papers[:3] if p.get("title")]
        named = "、".join(f"《{title}》" for title in titles)
        if plan.search_mode in {"author", "mixed"} and plan.author_hints:
            answer = f"已按作者「{plan.author_hints[0]}」完成匹配，共找到 {total} 篇相关论文。"
        else:
            keywords = "、".join(plan.keywords[:5]) or query
            answer = f"已根据“{keywords}”完成智能匹配，共找到 {total} 篇相关论文。"
        if named:
            answer += f" 其中较相关的包括：{named}。"
        if plan.intent:
            answer += f" 检索意图：{plan.intent}"
        return SearchAnswer(answer=answer, highlights=(plan.author_hints or plan.keywords)[:5], source="template")


def _merge_plans(heuristic: SearchPlan, llm: SearchPlan) -> SearchPlan:
    """Prefer LLM phrasing, but keep deterministic author romanization / arxiv detection."""
    authors = _dedupe([*(llm.author_hints or []), *(heuristic.author_hints or [])])[:6]
    keywords = _dedupe([*(llm.keywords or []), *(heuristic.keywords or [])])[:5]
    categories = _dedupe([*(llm.category_hints or []), *(heuristic.category_hints or [])])[:3]
    mode = llm.search_mode if llm.search_mode != "topic" or heuristic.search_mode == "topic" else heuristic.search_mode
    if heuristic.search_mode == "arxiv":
        mode = "arxiv"
        keywords = heuristic.keywords or keywords
    if heuristic.search_mode in {"author", "mixed"} and authors:
        mode = heuristic.search_mode if llm.search_mode not in {"author", "mixed"} else llm.search_mode
    rewritten = llm.rewritten_query or heuristic.rewritten_query
    if mode == "author" and authors:
        rewritten = authors[0]
    return SearchPlan(
        rewritten_query=rewritten,
        keywords=keywords or heuristic.keywords,
        author_hints=authors,
        category_hints=categories,
        search_mode=mode,
        intent=llm.intent or heuristic.intent,
        source="llm",
    )


_HEURISTIC_STOP = {
    "a", "an", "the", "and", "or", "of", "in", "on", "for", "to", "with", "via", "by",
    "from", "using", "based", "paper", "study", "method", "model", "models", "learning",
    "data", "approach", "towards", "toward", "一种", "基于", "通过", "研究", "方法", "模型", "论文",
    "老师", "教授", "博士", "找一下", "帮我", "搜索", "查找",
}


def _heuristic_keywords(query: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}|[\u4e00-\u9fff]{2,}", query or "")
    expanded = list(expand_query_tokens(query))
    merged = _dedupe(
        [
            token
            for token in tokens + [t for t in expanded if re.search(r"[A-Za-z]", t) or len(t) >= 2]
            if token.casefold() not in _HEURISTIC_STOP
        ]
    )
    # Drop Chinese person-name tokens once romanized elsewhere
    merged = [token for token in merged if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", token)]
    if len(merged) < 2 and query.strip() and query.strip() not in merged:
        cleaned = strip_query_fillers(query)
        if cleaned and cleaned not in merged:
            merged.insert(0, cleaned)
    return merged[:5]


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
