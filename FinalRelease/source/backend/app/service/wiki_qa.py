"""Build grounded QA evidence from paper Wiki (structured parse results)."""

from __future__ import annotations

from typing import Any

from app.schema.papers import WikiData
from app.service.qa_citations import score_chunk


def wiki_item_text(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        parts = [
            item.get("name"),
            item.get("title"),
            item.get("description"),
            item.get("text"),
            item.get("detail"),
            item.get("limitation"),
        ]
        return "\n".join(str(part).strip() for part in parts if part and str(part).strip())
    return str(item).strip()


def wiki_has_content(wiki: WikiData) -> bool:
    if (wiki.summary or "").strip():
        return True
    for group in (wiki.concepts, wiki.methods, wiki.experiments, wiki.limitations):
        for item in group or []:
            if wiki_item_text(item):
                return True
    return False


def build_wiki_evidence(
    wiki: WikiData,
    question: str,
    *,
    top_k: int = 8,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Turn Wiki fields into QA evidence dicts compatible with QaAgent / citations."""
    candidates: list[dict[str, Any]] = []
    summary = (wiki.summary or "").strip()
    if summary:
        candidates.append(
            {
                "chunk_id": "wiki-summary",
                "page_no": None,
                "section": "wiki_summary",
                "section_title": "Wiki·摘要",
                "content": summary,
                "source": "wiki",
            }
        )

    for index, item in enumerate(wiki.concepts or []):
        text = wiki_item_text(item)
        if not text:
            continue
        name = str(item.get("name") or "").strip() if isinstance(item, dict) else ""
        candidates.append(
            {
                "chunk_id": f"wiki-concept-{index}",
                "page_no": None,
                "section": "wiki_concept",
                "section_title": f"Wiki·概念{('·' + name) if name else ''}",
                "content": text,
                "source": "wiki",
            }
        )

    for index, item in enumerate(wiki.methods or []):
        text = wiki_item_text(item)
        if not text:
            continue
        title = str(item.get("title") or "").strip() if isinstance(item, dict) else ""
        candidates.append(
            {
                "chunk_id": f"wiki-method-{index}",
                "page_no": None,
                "section": "wiki_method",
                "section_title": f"Wiki·方法{('·' + title) if title else ''}",
                "content": text,
                "source": "wiki",
            }
        )

    for index, item in enumerate(wiki.experiments or []):
        text = wiki_item_text(item)
        if not text:
            continue
        title = ""
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or "").strip()
        candidates.append(
            {
                "chunk_id": f"wiki-experiment-{index}",
                "page_no": None,
                "section": "wiki_experiment",
                "section_title": f"Wiki·实验{('·' + title) if title else ''}",
                "content": text,
                "source": "wiki",
            }
        )

    for index, item in enumerate(wiki.limitations or []):
        text = wiki_item_text(item)
        if not text:
            continue
        candidates.append(
            {
                "chunk_id": f"wiki-limitation-{index}",
                "page_no": None,
                "section": "wiki_limitation",
                "section_title": "Wiki·局限",
                "content": text,
                "source": "wiki",
            }
        )

    if not candidates:
        return []

    q = (question or "").casefold()
    type_boost = {
        "wiki_summary": 0.04 if any(k in q for k in ("摘要", "总结", "讲了什么", "贡献", "创新", "overview", "summary")) else 0.02,
        "wiki_concept": 0.05 if any(k in q for k in ("概念", "定义", "术语", "concept")) else 0.01,
        "wiki_method": 0.06 if any(k in q for k in ("方法", "模型", "算法", "架构", "method", "approach")) else 0.01,
        "wiki_experiment": 0.06 if any(k in q for k in ("实验", "结果", "数据", "指标", "experiment", "result")) else 0.01,
        "wiki_limitation": 0.06 if any(k in q for k in ("局限", "不足", "未来", "limitation", "future")) else 0.01,
    }

    scored: list[dict[str, Any]] = []
    for item in candidates:
        base = float(score_chunk(question, item["content"]))
        boost = float(type_boost.get(str(item.get("section") or ""), 0.01))
        score = base + boost
        if score < min_score:
            continue
        scored.append({**item, "score": score})

    if not scored:
        scored = [
            {**item, "score": 0.05 + type_boost.get(str(item.get("section") or ""), 0.01)}
            for item in candidates
        ]

    scored.sort(
        key=lambda item: (float(item["score"]), len(item.get("content") or ""), item["chunk_id"]),
        reverse=True,
    )
    return scored[:top_k]


__all__ = ["build_wiki_evidence", "wiki_has_content", "wiki_item_text"]
