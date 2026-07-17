"""Retrieval and citation helpers for grounded paper QA."""

from __future__ import annotations

import re
from typing import Any

_STOPWORDS = {
    "a", "an", "and", "are", "be", "by", "can", "do", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "what", "when", "where", "which", "who", "why", "with", "这篇", "论文",
}
_QUERY_EXPANSION = {
    "创新": ["propose", "novel", "contribution", "architecture"],
    "核心": ["main", "contribution", "key"],
    "方法": ["method", "approach", "architecture", "model", "algorithm"],
    "模型": ["model", "architecture", "network", "transformer"],
    "实验": ["experiment", "result", "evaluation", "dataset", "benchmark"],
    "结果": ["result", "performance", "outperform", "bleu", "accuracy"],
    "局限": ["limitation", "drawback", "future work"],
    "注意力": ["attention", "self-attention", "multi-head"],
    "训练": ["training", "optimizer", "learn"],
}


def tokens(value: str) -> set[str]:
    normalized = (value or "").casefold()
    english = {
        item for item in re.findall(r"[a-z0-9]+", normalized)
        if len(item) > 1 and item not in _STOPWORDS
    }
    chinese: set[str] = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        chinese.update(run[index : index + 2] for index in range(len(run) - 1))
        chinese.add(run)
    return english | chinese


def expand_query_tokens(query: str) -> set[str]:
    expanded = tokens(query)
    for keyword, additions in _QUERY_EXPANSION.items():
        if keyword in query:
            for addition in additions:
                expanded.update(tokens(addition))
    if not any(re.search(r"[a-z]", item) for item in expanded) and re.search(r"[\u4e00-\u9fff]", query):
        expanded.update({"method", "model", "attention", "result", "experiment"})
    return expanded


def score_chunk(query: str, content: str) -> float:
    query_tokens = expand_query_tokens(query)
    content_tokens = tokens(content)
    if not query_tokens:
        return 0.0
    score = len(query_tokens & content_tokens) / len(query_tokens)
    if query.casefold() in (content or "").casefold():
        score += 0.5
    if len(content or "") >= 120:
        score += 0.05
    if is_noisy_chunk(content):
        score -= 0.2
    return score


def support_score(answer: str, content: str) -> float:
    answer_tokens = expand_query_tokens(answer)
    content_tokens = tokens(content)
    if not answer_tokens or not content_tokens:
        return 0.0
    return len(answer_tokens & content_tokens) / max(min(len(answer_tokens), 16), 1)


def is_noisy_chunk(content: str) -> bool:
    lowered = (content or "").casefold()
    return any(marker in lowered for marker in ("permission to reproduce", "provided proper attribution", "arxiv:", "table of contents"))


def polish_quote(content: str, *, answer: str = "", max_len: int = 280) -> str:
    text = re.sub(r"\s+", " ", (content or "")).strip()
    if not text:
        return ""
    sentences = [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+", text) if len(item.strip()) >= 40]
    chosen = max(sentences, key=lambda item: support_score(answer, item)) if sentences and answer else (sentences[0] if sentences else text)
    if len(chosen) <= max_len:
        return chosen
    return chosen[:max_len].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def select_relevant_chunk_ids(
    *,
    answer: str,
    evidence: list[dict[str, Any]],
    preferred_ids: list[str] | None = None,
    min_overlap: float = 0.08,
    max_citations: int = 3,
) -> list[str]:
    by_id = {str(item["chunk_id"]): item for item in evidence}
    selected: list[str] = []
    for chunk_id in preferred_ids or []:
        item = by_id.get(str(chunk_id))
        if item is None or is_noisy_chunk(item.get("content") or ""):
            continue
        if support_score(answer, item.get("content") or "") >= max(0.03, min_overlap * 0.4) or len(item.get("content") or "") >= 100:
            selected.append(str(chunk_id))
        if len(selected) >= max_citations:
            return selected
    if selected:
        return selected
    for item in sorted(evidence, key=lambda row: support_score(answer, row.get("content") or ""), reverse=True):
        content = item.get("content") or ""
        chunk_id = str(item["chunk_id"])
        if not is_noisy_chunk(content) and support_score(answer, content) >= min_overlap and chunk_id not in selected:
            selected.append(chunk_id)
        if len(selected) >= max_citations:
            break
    return selected


def section_label(section: str | None, content: str) -> str:
    if section and section not in {"body", "unknown"}:
        return section
    lowered = (content or "")[:200].casefold()
    for marker, label in (("abstract", "Abstract"), ("introduction", "Introduction"), ("attention", "Method"), ("experiment", "Experiments"), ("result", "Results"), ("conclusion", "Conclusion")):
        if marker in lowered:
            return label
    return "原文"


__all__ = ["polish_quote", "score_chunk", "section_label", "select_relevant_chunk_ids"]
