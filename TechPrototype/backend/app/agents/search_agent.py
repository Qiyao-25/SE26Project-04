"""Search Agent - natural language query rewrite + search answer generation."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings
from app.service.qa_citations import expand_query_tokens
from app.service.search_query_normalize import (
    expand_chinese_topics,
    expand_term_aliases,
    extract_arxiv_id,
    extract_exclude_terms,
    extract_year_range,
    infer_search_mode,
    resolve_author_hints,
    romanize_chinese_person_name,
    strip_query_fillers,
)


REWRITE_PROMPT = """你是 PaperMate Academic Search Planner。
把用户问题解析为保守、可执行的论文检索计划。数据库作者多为英文（Beijun Shen），标题/摘要多为英文。

只输出 JSON：
{
  "rewritten_query": "简短检索短语（优先英文）",
  "keywords": ["keyword1"],
  "author_hints": ["Beijun Shen"],
  "category_hints": ["cs.CL"],
  "search_mode": "topic|author|mixed|arxiv|title|overview",
  "intent": "一句话意图",
  "year_from": null,
  "year_to": null,
  "exclude_terms": [],
  "warnings": []
}

规则：
1. 口语填充词不要进入 keywords。
2. 汉语人名：可信映射才写入确定 author_hints；不确定音译加入 warnings: AUTHOR_TRANSLITERATION_UNVERIFIED，仍可给候选英文变体。
3. 作者检索 search_mode=author；作者+主题=mixed；编号=arxiv；完整标题=title；「代表/进展」类=overview。
4. 中文主题改写为常用英文词；可用常见别名（RAG/LLM/LoRA），禁止 model/method/paper/research/研究/方法 等泛词。
5. 硬条件必须保留：年份、分类、排除（不要综述→survey/review）、arXiv ID。
6. 「代表/最新/最佳/所有」改写为当前库范围，并在 warnings 说明。
7. 同一意图输出稳定 keywords；不确定人名不要断言为同一人。
"""


ANSWER_PROMPT = """你是 PaperMate Search Result Summarizer。只能依据用户问题和给定候选论文元数据回答。
只输出 JSON：
{
  "answer": "2-5句中文说明，仅描述当前库命中",
  "highlights": ["匹配要点"],
  "cited_paper_ids": [1, 2]
}
规则：
1. cited_paper_ids 必须是给定候选的 paper_id 子集。
2. 不得声称库外事实、引用量、SOTA 或完整领域结论。
3. 作者检索时对照英文作者名，不编造作者关系。
4. 无足够证据时说明库覆盖不足。不要输出 Markdown，不要输出空「出处」。
"""


@dataclass
class SearchPlan:
    rewritten_query: str
    keywords: list[str] = field(default_factory=list)
    author_hints: list[str] = field(default_factory=list)
    author_verified: bool = False
    category_hints: list[str] = field(default_factory=list)
    search_mode: str = "topic"
    intent: str = ""
    source: str = "heuristic"
    arxiv_ids: list[str] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    exclude_terms: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    plan_confidence: float = 0.55

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SearchPlan":
        data = data or {}
        return cls(
            rewritten_query=str(data.get("rewritten_query") or ""),
            keywords=_as_str_list(data.get("keywords")),
            author_hints=_as_str_list(data.get("author_hints")),
            author_verified=bool(data.get("author_verified")),
            category_hints=_as_str_list(data.get("category_hints")),
            search_mode=str(data.get("search_mode") or "topic"),
            intent=str(data.get("intent") or ""),
            source=str(data.get("source") or "reused"),
            arxiv_ids=_as_str_list(data.get("arxiv_ids")),
            year_from=_as_optional_int(data.get("year_from")),
            year_to=_as_optional_int(data.get("year_to")),
            exclude_terms=_as_str_list(data.get("exclude_terms")),
            aliases=_as_str_list(data.get("aliases")),
            warnings=_as_str_list(data.get("warnings")),
            plan_confidence=float(data.get("plan_confidence") or 0.5),
        )


@dataclass
class SearchAnswer:
    answer: str
    highlights: list[str] = field(default_factory=list)
    cited_paper_ids: list[int] = field(default_factory=list)
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
                return _merge_plans(heuristic, self._plan_with_llm(query))
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
        if mode not in {"topic", "author", "mixed", "arxiv", "title", "overview"}:
            mode = infer_search_mode(query, author_hints=author_hints)
        if not keywords:
            keywords = _heuristic_keywords(query)
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
            year_from=_as_optional_int(data.get("year_from")),
            year_to=_as_optional_int(data.get("year_to")),
            exclude_terms=_as_str_list(data.get("exclude_terms"))[:8],
            warnings=_as_str_list(data.get("warnings"))[:8],
            plan_confidence=0.72,
        )

    def _plan_heuristic(self, query: str) -> SearchPlan:
        arxiv_id = extract_arxiv_id(query)
        authors, author_verified, author_warnings = resolve_author_hints(query)
        topic_kw, categories = expand_chinese_topics(query)
        canonical, aliases, lex_cats = expand_term_aliases(query)
        year_from, year_to = extract_year_range(query)
        excludes = extract_exclude_terms(query)
        mode = infer_search_mode(query, author_hints=authors)
        cleaned = strip_query_fillers(query)
        warnings = list(author_warnings)
        if re.search(r"代表|最新|最佳|所有|经典", query or ""):
            warnings.append("SCOPE_LIMITED_TO_LOCAL_LIBRARY")
            if mode == "topic":
                mode = "overview"

        if arxiv_id:
            return SearchPlan(
                rewritten_query=arxiv_id,
                keywords=[arxiv_id],
                arxiv_ids=[arxiv_id],
                search_mode="arxiv",
                intent=f"按 arXiv 编号检索 {arxiv_id}",
                source="heuristic",
                plan_confidence=0.95,
            )

        keywords: list[str] = []
        if mode in {"author", "mixed"} and authors:
            keywords.extend(authors[:3])
        keywords.extend(canonical[:3])
        keywords.extend(topic_kw)
        if mode in {"topic", "overview", "mixed"}:
            keywords.extend(_heuristic_keywords(cleaned))
        keywords = _dedupe([k for k in keywords if k.casefold() not in _HEURISTIC_STOP])[:5]

        rewritten = authors[0] if mode == "author" and authors else (canonical[0] if canonical else (topic_kw[0] if topic_kw else cleaned))
        if mode == "mixed" and authors and (canonical or topic_kw):
            rewritten = f"{authors[0]} {(canonical or topic_kw)[0]}"

        intent = {
            "author": f"按作者检索：{authors[0] if authors else cleaned}",
            "mixed": f"按作者与主题检索：{rewritten}",
            "overview": f"库内主题概览：{rewritten}",
            "topic": "基于关键词的模糊匹配",
        }.get(mode, "基于关键词的模糊匹配")

        return SearchPlan(
            rewritten_query=rewritten,
            keywords=keywords or _heuristic_keywords(cleaned) or [cleaned],
            author_hints=authors[:6],
            author_verified=author_verified,
            category_hints=_dedupe([*categories, *lex_cats])[:3],
            search_mode=mode,
            intent=intent,
            source="heuristic",
            year_from=year_from,
            year_to=year_to,
            exclude_terms=excludes,
            aliases=aliases[:12],
            warnings=_dedupe(warnings),
            plan_confidence=0.6 if author_verified or canonical else 0.5,
        )

    def _answer_with_llm(self, *, query: str, plan: SearchPlan, papers: list[dict[str, Any]], total: int) -> SearchAnswer:
        allowed_ids = {int(p["paper_id"]) for p in papers if p.get("paper_id") is not None}
        lines = []
        for index, paper in enumerate(papers[:8], start=1):
            lines.append(
                f"{index}. id={paper.get('paper_id')} | {paper.get('title')} | "
                f"authors={', '.join(paper.get('authors') or [])} | "
                f"cat={paper.get('primary_category')} | abstract={(paper.get('abstract') or '')[:180]}"
            )
        user_prompt = (
            f"用户问题：{query}\n"
            f"检索意图：{plan.intent or plan.rewritten_query}\n"
            f"检索模式：{plan.search_mode}\n"
            f"作者提示：{', '.join(plan.author_hints) or '无'}（verified={plan.author_verified}）\n"
            f"关键词：{', '.join(plan.keywords)}\n"
            f"警告：{', '.join(plan.warnings) or '无'}\n"
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
        cited = []
        for item in data.get("cited_paper_ids") or []:
            try:
                pid = int(item)
            except (TypeError, ValueError):
                continue
            if pid in allowed_ids:
                cited.append(pid)
        return SearchAnswer(
            answer=answer,
            highlights=_as_str_list(data.get("highlights"))[:5],
            cited_paper_ids=cited[:5],
            source="llm",
        )

    def _answer_template(self, *, query: str, plan: SearchPlan, papers: list[dict[str, Any]], total: int) -> SearchAnswer:
        if total <= 0:
            hint = ""
            if plan.author_hints:
                hint = f" 可尝试英文作者名「{plan.author_hints[0]}」。"
            if "AUTHOR_TRANSLITERATION_UNVERIFIED" in plan.warnings:
                hint += " 当前人名映射未经权威别名表确认。"
            return SearchAnswer(
                answer=f"当前库中未找到与“{query}”匹配的论文。{hint}也可尝试更短的英文主题词或放宽年份/分类。".strip(),
                source="template",
            )
        titles = [str(p.get("title") or "") for p in papers[:3] if p.get("title")]
        named = "、".join(f"《{title}》" for title in titles)
        if plan.search_mode in {"author", "mixed"} and plan.author_hints:
            answer = f"已按作者「{plan.author_hints[0]}」在当前库中匹配，共找到 {total} 篇相关论文。"
        else:
            keywords = "、".join(plan.keywords[:5]) or query
            answer = f"当前库中根据“{keywords}”找到 {total} 篇相关论文。"
        if named:
            answer += f" 其中较相关的包括：{named}。"
        if plan.year_from or plan.year_to:
            answer += f" 已应用年份过滤：{plan.year_from or '…'}–{plan.year_to or '…'}。"
        if plan.exclude_terms:
            answer += f" 已排除：{'/'.join(plan.exclude_terms[:3])}。"
        if plan.warnings:
            answer += "（已按当前库范围说明，非外部权威排名。）"
        cited = [int(p["paper_id"]) for p in papers[:3] if p.get("paper_id") is not None]
        return SearchAnswer(
            answer=answer,
            highlights=(plan.author_hints or plan.keywords)[:5],
            cited_paper_ids=cited,
            source="template",
        )


def _merge_plans(heuristic: SearchPlan, llm: SearchPlan) -> SearchPlan:
    authors = _dedupe([*(llm.author_hints or []), *(heuristic.author_hints or [])])[:6]
    keywords = _dedupe([*(llm.keywords or []), *(heuristic.keywords or [])])[:5]
    categories = _dedupe([*(llm.category_hints or []), *(heuristic.category_hints or [])])[:3]
    excludes = _dedupe([*(llm.exclude_terms or []), *(heuristic.exclude_terms or [])])[:8]
    warnings = _dedupe([*(llm.warnings or []), *(heuristic.warnings or [])])[:8]
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
        author_verified=heuristic.author_verified or llm.author_verified,
        category_hints=categories,
        search_mode=mode,
        intent=llm.intent or heuristic.intent,
        source="llm",
        arxiv_ids=_dedupe([*heuristic.arxiv_ids, *llm.arxiv_ids])[:3],
        year_from=llm.year_from if llm.year_from is not None else heuristic.year_from,
        year_to=llm.year_to if llm.year_to is not None else heuristic.year_to,
        exclude_terms=excludes,
        aliases=_dedupe([*heuristic.aliases, *llm.aliases])[:12],
        warnings=warnings,
        plan_confidence=max(heuristic.plan_confidence, llm.plan_confidence),
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
    merged = [token for token in merged if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", token)]
    if len(merged) < 2 and query.strip():
        cleaned = strip_query_fillers(query)
        if cleaned and cleaned not in merged:
            merged.insert(0, cleaned)
    return merged[:5]


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := str(item or "").strip())]


def _as_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
