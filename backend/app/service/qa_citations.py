"""Citation helpers for paper QA: retrieval expansion, quote polish, relevance filter."""

from __future__ import annotations

import re
from typing import Any

_EN_STOPWORDS = {
    "a", "an", "and", "are", "be", "by", "can", "do", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "what", "when", "where", "which", "who", "why", "with", "这篇", "论文",
}

# 中文意图 → 英文检索扩展（arXiv 原文多为英文）
_CN_QUERY_EXPAND: dict[str, list[str]] = {
    "创新": ["propose", "novel", "contribution", "attention", "transformer", "architecture"],
    "核心": ["propose", "key", "main", "contribution"],
    "方法": ["method", "approach", "architecture", "model", "network", "algorithm"],
    "模型": ["model", "architecture", "network", "transformer"],
    "实验": ["experiment", "result", "evaluation", "bleu", "accuracy", "dataset", "benchmark"],
    "结果": ["result", "bleu", "performance", "outperform", "sota"],
    "局限": ["limitation", "drawback", "future work", "although"],
    "注意力": ["attention", "self-attention", "multi-head"],
    "摘要": ["abstract", "summary"],
    "介绍": ["introduction"],
    "训练": ["training", "optimizer", "learn"],
    "翻译": ["translation", "bleu", "wmt", "machine translation"],
    "解码": ["decoder", "decoding"],
    "编码": ["encoder", "encoding"],
}


def tokens(value: str) -> set[str]:
    normalized = (value or "").casefold()
    english = {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 1 and token not in _EN_STOPWORDS
    }
    chinese: set[str] = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        chinese.update(run[index : index + 2] for index in range(len(run) - 1))
        if len(run) >= 2:
            chinese.add(run)
    return english | chinese


def expand_query_tokens(query: str) -> set[str]:
    base = tokens(query)
    expanded = set(base)
    raw = query or ""
    for cn, en_list in _CN_QUERY_EXPAND.items():
        if cn in raw:
            expanded.update(en_list)
            for term in en_list:
                expanded.update(tokens(term))
    # 纯中文提问时补一组通用学术词，避免检索全空
    if not any(re.search(r"[a-z]", t) for t in expanded) and re.search(r"[\u4e00-\u9fff]", raw):
        expanded.update({"propose", "method", "model", "attention", "result", "experiment", "architecture"})
    return expanded


def score_chunk(query: str, content: str) -> float:
    query_tokens = expand_query_tokens(query)
    if not query_tokens:
        return 0.0
    content_tokens = tokens(content)
    overlap = len(query_tokens & content_tokens)
    score = overlap / max(len(query_tokens), 1)
    q = query.casefold()
    c = (content or "").casefold()
    if q and q in c:
        score += 0.5
    # 质量加权：完整句子、足够长度
    if len(content or "") >= 120:
        score += 0.05
    if re.search(r"[.!?。；]\s+[A-Z\u4e00-\u9fff]", content or ""):
        score += 0.02
    # 惩罚明显页眉/版权噪声
    noise = ("permission to reproduce", "arxiv:", "provided proper attribution", "table of contents")
    if any(n in c for n in noise):
        score -= 0.2
    return score


def support_score(answer: str, content: str) -> float:
    """Bilingual-aware relevance between answer and English/Chinese evidence."""
    ans_tokens = expand_query_tokens(answer)
    content_tokens = tokens(content)
    if not ans_tokens or not content_tokens:
        return 0.0
    denom = max(min(len(ans_tokens), 16), 1)
    return len(ans_tokens & content_tokens) / denom


def is_noisy_chunk(content: str) -> bool:
    c = (content or "").lower()
    return any(
        marker in c
        for marker in (
            "permission to reproduce",
            "provided proper attribution",
            "arxiv:",
            "table of contents",
        )
    )


def polish_quote(content: str, *, answer: str = "", max_len: int = 280) -> str:
    """Pick a readable sentence/snippet; avoid mid-word truncation."""
    text = re.sub(r"\s+", " ", (content or "")).strip()
    if not text:
        return ""

    # Drop leading fragment that starts mid-word (e.g. "tworks that...")
    if text and text[0].islower():
        m = re.search(r"[.!?]\s+([A-Z].*)", text)
        if m:
            text = m.group(1).strip()
        else:
            parts = text.split(" ", 1)
            text = parts[1].strip() if len(parts) > 1 else text

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?。！？])\s+", text)
        if len(s.strip()) >= 40
    ]
    if not sentences:
        snippet = text[:max_len].strip()
        if len(text) > max_len:
            cut = snippet.rsplit(" ", 1)[0]
            snippet = (cut or snippet).rstrip(",;:") + "…"
        return snippet

    if answer.strip():
        ranked = sorted(sentences, key=lambda s: support_score(answer, s), reverse=True)
        best = ranked[0]
    else:
        best = max(sentences, key=len)

    if len(best) <= max_len:
        return best
    cut = best[:max_len].rsplit(" ", 1)[0]
    return (cut or best[:max_len]).rstrip(",;:") + "…"


def select_relevant_chunk_ids(
    *,
    answer: str,
    evidence: list[dict[str, Any]],
    preferred_ids: list[str] | None = None,
    min_overlap: float = 0.08,
    max_citations: int = 3,
) -> list[str]:
    """Keep citations that support the answer; drop noise / unrelated filler."""
    by_id = {str(item["chunk_id"]): item for item in evidence}
    selected: list[str] = []

    for cid in preferred_ids or []:
        item = by_id.get(str(cid))
        if item is None:
            continue
        content = item.get("content") or ""
        if is_noisy_chunk(content):
            continue
        # Agent 已点名的证据：只要不是噪声且有一定支撑分就保留
        if support_score(answer, content) >= max(0.03, min_overlap * 0.4) or len(content) >= 100:
            if str(cid) not in selected:
                selected.append(str(cid))
        if len(selected) >= max_citations:
            return selected

    if selected:
        return selected

    ranked = sorted(
        evidence,
        key=lambda item: support_score(answer, item.get("content") or ""),
        reverse=True,
    )
    for item in ranked:
        content = item.get("content") or ""
        if is_noisy_chunk(content):
            continue
        if support_score(answer, content) < min_overlap:
            continue
        cid = str(item["chunk_id"])
        if cid not in selected:
            selected.append(cid)
        if len(selected) >= max_citations:
            break
    return selected


def section_label(section: str | None, content: str) -> str:
    if section and section not in {"body", "unknown"}:
        return section
    head = (content or "")[:200].lower()
    for key, label in (
        ("abstract", "Abstract"),
        ("introduction", "Introduction"),
        ("related work", "Related Work"),
        ("attention", "Method"),
        ("experiment", "Experiments"),
        ("result", "Results"),
        ("conclusion", "Conclusion"),
    ):
        if key in head:
            return label
    return "原文"


__all__ = [
    "expand_query_tokens",
    "polish_quote",
    "score_chunk",
    "section_label",
    "select_relevant_chunk_ids",
    "support_score",
    "tokens",
]
