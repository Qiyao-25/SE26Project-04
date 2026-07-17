"""Knowledge-graph & research-lineage Agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings


SYSTEM_PROMPT = """你是 PaperMate 的研究脉络与知识图谱 Agent。
根据当前论文、已抽取的概念/方法，以及候选相关论文，输出 JSON：
{
  "narrative": "一段中文主题演进说明（3-6句）",
  "entities": [
    {"id": "e1", "type": "concept|method|dataset|task", "label": "名称"}
  ],
  "relations": [
    {"source": "paper", "target": "e1", "type": "introduces|uses|extends|related_to", "label": "中文短标签"}
  ],
  "lineage": [
    {"paper_ref": "候选论文的 arxiv_id 或标题关键字", "role": "precursor|current|followup|related", "note": "一句关系说明"}
  ]
}
规则：
1. entities 不超过 10 个；relations 不超过 16 条；lineage 不超过 8 条。
2. 当前论文在 relations 里用 source/target = "paper"。
3. 不要编造不存在的论文；lineage.paper_ref 必须能对应候选列表。
4. 只输出 JSON。
"""


@dataclass
class PaperGraph:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    lineage: list[dict[str, Any]] = field(default_factory=list)
    narrative: str = ""
    source: str = "heuristic"

    def to_structured_rows(self) -> list[dict[str, Any]]:
        locator = {"source": self.source}
        return [
            {
                "result_type": "kg_graph",
                "version": 1,
                "content_json": {"nodes": self.nodes, "edges": self.edges, "source": self.source},
                "source_locator": locator,
                "confidence": 0.75 if self.source.startswith("llm") else 0.55,
            },
            {
                "result_type": "topic_lineage",
                "version": 1,
                "content_json": {"items": self.lineage, "narrative": self.narrative, "source": self.source},
                "source_locator": locator,
                "confidence": 0.7 if self.source.startswith("llm") else 0.5,
            },
        ]


class GraphAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        *,
        paper_id: int,
        title: str,
        abstract: str,
        arxiv_id: str = "",
        primary_category: str = "",
        published_at: str = "",
        concepts: list[dict[str, Any]] | None = None,
        methods: list[dict[str, Any]] | None = None,
        related_papers: list[dict[str, Any]] | None = None,
    ) -> PaperGraph:
        concepts = concepts or []
        methods = methods or []
        related_papers = related_papers or []

        base = _heuristic_graph(
            paper_id=paper_id,
            title=title,
            arxiv_id=arxiv_id,
            primary_category=primary_category,
            published_at=published_at,
            concepts=concepts,
            methods=methods,
            related_papers=related_papers,
        )

        if not getattr(self.settings, "graph_agent_enabled", True):
            return base
        if not (self.settings.llm_api_key.strip() and self.settings.llm_model.strip()):
            return base

        try:
            enriched = self._llm_enrich(
                title=title,
                abstract=abstract,
                arxiv_id=arxiv_id,
                concepts=concepts,
                methods=methods,
                related_papers=related_papers,
                base=base,
            )
            return enriched
        except Exception:  # noqa: BLE001 — fall back to heuristic graph
            return base

    def _llm_enrich(
        self,
        *,
        title: str,
        abstract: str,
        arxiv_id: str,
        concepts: list[dict[str, Any]],
        methods: list[dict[str, Any]],
        related_papers: list[dict[str, Any]],
        base: PaperGraph,
    ) -> PaperGraph:
        related_brief = [
            {
                "paper_id": item.get("paper_id"),
                "arxiv_id": item.get("arxiv_id"),
                "title": item.get("title"),
                "published_at": item.get("published_at"),
                "primary_category": item.get("primary_category"),
            }
            for item in related_papers[:10]
        ]
        user_payload = {
            "current_paper": {"arxiv_id": arxiv_id, "title": title, "abstract": (abstract or "")[:1800]},
            "concepts": [{"name": c.get("name"), "description": (c.get("description") or "")[:120]} for c in concepts[:8]],
            "methods": [{"title": m.get("title"), "description": (m.get("description") or "")[:120]} for m in methods[:6]],
            "related_candidates": related_brief,
        }
        raw = chat_completion(
            api_key=self.settings.llm_api_key,
            api_base=self.settings.llm_api_base,
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            timeout_s=float(getattr(self.settings, "graph_agent_timeout_s", 60.0)),
            json_mode=True,
        )
        data = json.loads(_strip_fence(raw))
        if not isinstance(data, dict):
            raise LlmError("Graph Agent JSON 根节点必须是对象")
        return _merge_llm_graph(base, data, related_papers)


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _node(node_id: str, node_type: str, label: str, **extra: Any) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "label": (label or node_id)[:80], **extra}


def _edge(edge_id: str, source: str, target: str, edge_type: str, label: str = "") -> dict[str, Any]:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "type": edge_type,
        "label": label or edge_type,
    }


def _heuristic_graph(
    *,
    paper_id: int,
    title: str,
    arxiv_id: str,
    primary_category: str,
    published_at: str,
    concepts: list[dict[str, Any]],
    methods: list[dict[str, Any]],
    related_papers: list[dict[str, Any]],
) -> PaperGraph:
    paper_node_id = f"paper-{paper_id}"
    nodes = [
        _node(
            paper_node_id,
            "paper",
            title or arxiv_id or f"Paper {paper_id}",
            paper_id=paper_id,
            arxiv_id=arxiv_id,
            role="current",
            published_at=published_at,
        )
    ]
    edges: list[dict[str, Any]] = []

    for index, concept in enumerate(concepts[:6], 1):
        cid = f"concept-{index}"
        name = str(concept.get("name") or f"概念{index}")
        nodes.append(_node(cid, "concept", name, description=str(concept.get("description") or "")[:200]))
        edges.append(_edge(f"e-c-{index}", paper_node_id, cid, "introduces", "提出/涉及"))

    for index, method in enumerate(methods[:5], 1):
        mid = f"method-{index}"
        name = str(method.get("title") or method.get("name") or f"方法{index}")
        nodes.append(_node(mid, "method", name, description=str(method.get("description") or "")[:200]))
        edges.append(_edge(f"e-m-{index}", paper_node_id, mid, "uses", "使用方法"))

    if primary_category:
        cat_id = "category-1"
        nodes.append(_node(cat_id, "task", primary_category))
        edges.append(_edge("e-cat", paper_node_id, cat_id, "related_to", "领域"))

    lineage: list[dict[str, Any]] = [
        {
            "paper_id": paper_id,
            "arxiv_id": arxiv_id,
            "title": title,
            "published_at": published_at,
            "role": "current",
            "note": "当前阅读论文",
        }
    ]

    current_year = _year(published_at)
    for index, related in enumerate(related_papers[:8], 1):
        rid = int(related.get("paper_id") or 0)
        if not rid or rid == paper_id:
            continue
        rtitle = str(related.get("title") or related.get("arxiv_id") or f"paper-{rid}")
        rpublished = str(related.get("published_at") or "")
        role = _infer_role(current_year, _year(rpublished))
        # 相关论文只进入脉络/列表，不塞进主图谱节点，避免可视化不可读
        lineage.append(
            {
                "paper_id": rid,
                "arxiv_id": related.get("arxiv_id") or "",
                "title": rtitle,
                "published_at": rpublished,
                "role": role,
                "note": "库内主题相近论文",
            }
        )

    lineage.sort(key=lambda item: (item.get("published_at") or "9999", item.get("paper_id") or 0))
    narrative = _default_narrative(title, concepts, lineage)
    return PaperGraph(nodes=nodes, edges=edges, lineage=lineage, narrative=narrative, source="heuristic")


def _infer_role(current_year: int | None, other_year: int | None) -> str:
    if current_year and other_year:
        if other_year < current_year:
            return "precursor"
        if other_year > current_year:
            return "followup"
    return "related"


def _year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group(0)) if match else None


def _default_narrative(title: str, concepts: list[dict[str, Any]], lineage: list[dict[str, Any]]) -> str:
    concept_names = [str(c.get("name")) for c in concepts[:3] if c.get("name")]
    concept_text = "、".join(concept_names) if concept_names else "相关核心概念"
    related_count = max(0, len(lineage) - 1)
    return (
        f"围绕《{title}》，图谱聚焦 {concept_text}。"
        f"当前从数据库匹配到 {related_count} 篇主题相近论文，按发表时间构成轻量研究脉络。"
        "关系边由概念/方法抽取与主题相似度共同生成，供阅读导航使用。"
    )


def _merge_llm_graph(base: PaperGraph, data: dict[str, Any], related_papers: list[dict[str, Any]]) -> PaperGraph:
    paper_node = next((n for n in base.nodes if n.get("type") == "paper" and n.get("role") == "current"), base.nodes[0])
    paper_node_id = paper_node["id"]

    nodes = [paper_node]
    edges: list[dict[str, Any]] = []
    id_map: dict[str, str] = {"paper": paper_node_id}

    for index, entity in enumerate(data.get("entities") or [], 1):
        if not isinstance(entity, dict):
            continue
        label = str(entity.get("label") or entity.get("name") or "").strip()
        if not label:
            continue
        etype = str(entity.get("type") or "concept").strip().lower()
        if etype not in {"concept", "method", "dataset", "task"}:
            etype = "concept"
        eid = str(entity.get("id") or f"ent-{index}")
        nid = f"{etype}-{index}"
        id_map[eid] = nid
        id_map[label.casefold()] = nid
        nodes.append(_node(nid, etype, label))

    # Keep only non-paper entities + current paper in the visual graph.
    # Related papers live in lineage for readability.
    related_by_key: dict[str, dict[str, Any]] = {}
    for item in related_papers:
        arxiv = str(item.get("arxiv_id") or "").casefold()
        title = str(item.get("title") or "").casefold()
        if arxiv:
            related_by_key[arxiv] = item
        if title:
            related_by_key[title[:40]] = item
        related_by_key[str(item.get("paper_id"))] = item

    for index, rel in enumerate(data.get("relations") or [], 1):
        if not isinstance(rel, dict):
            continue
        src = _resolve_endpoint(str(rel.get("source") or ""), id_map, paper_node_id)
        tgt = _resolve_endpoint(str(rel.get("target") or ""), id_map, paper_node_id)
        if not src or not tgt or src == tgt:
            continue
        edges.append(
            _edge(
                f"llm-e-{index}",
                src,
                tgt,
                str(rel.get("type") or "related_to"),
                str(rel.get("label") or rel.get("type") or "相关"),
            )
        )

    if not edges:
        edges = [e for e in base.edges if e.get("source") == paper_node_id or e.get("target") == paper_node_id]

    lineage = [
        item
        for item in base.lineage
        if item.get("role") == "current"
    ]
    for item in data.get("lineage") or []:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("paper_ref") or item.get("arxiv_id") or item.get("title") or "").strip()
        matched = _match_related(ref, related_papers, related_by_key)
        if matched is None:
            continue
        role = str(item.get("role") or matched.get("role") or "related")
        if role not in {"precursor", "current", "followup", "related"}:
            role = "related"
        lineage.append(
            {
                "paper_id": matched.get("paper_id"),
                "arxiv_id": matched.get("arxiv_id") or "",
                "title": matched.get("title") or ref,
                "published_at": matched.get("published_at") or "",
                "role": role,
                "note": str(item.get("note") or "主题相关").strip()[:200],
            }
        )

    # Ensure heuristic related papers remain if LLM lineage sparse
    seen = {int(x["paper_id"]) for x in lineage if x.get("paper_id") is not None}
    for item in base.lineage:
        pid = item.get("paper_id")
        if pid is None or int(pid) in seen:
            continue
        lineage.append(item)
        seen.add(int(pid))

    lineage.sort(key=lambda item: (item.get("published_at") or "9999", item.get("paper_id") or 0))
    narrative = str(data.get("narrative") or "").strip() or base.narrative
    # Deduplicate nodes by id
    uniq_nodes = []
    seen_ids = set()
    for node in nodes:
        if node["id"] in seen_ids:
            continue
        seen_ids.add(node["id"])
        uniq_nodes.append(node)
    return PaperGraph(nodes=uniq_nodes, edges=edges, lineage=lineage, narrative=narrative, source="llm_graph_agent")


def _resolve_endpoint(raw: str, id_map: dict[str, str], paper_node_id: str) -> str | None:
    key = raw.strip()
    if not key:
        return None
    if key in {"paper", "current", "self"}:
        return paper_node_id
    if key in id_map:
        return id_map[key]
    lowered = key.casefold()
    if lowered in id_map:
        return id_map[lowered]
    return None


def _match_related(
    ref: str,
    related_papers: list[dict[str, Any]],
    related_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not ref:
        return None
    lowered = ref.casefold()
    for key, item in related_by_key.items():
        if key and (key in lowered or lowered in key):
            return {
                "paper_id": item.get("paper_id"),
                "arxiv_id": item.get("arxiv_id") or "",
                "title": item.get("title") or item.get("label") or ref,
                "published_at": item.get("published_at") or "",
                "role": item.get("role") or "related",
            }
    for item in related_papers:
        arxiv = str(item.get("arxiv_id") or "").casefold()
        title = str(item.get("title") or "").casefold()
        if (arxiv and arxiv in lowered) or (title and (title[:24] in lowered or lowered in title)):
            return item
    return None


__all__ = ["GraphAgent", "PaperGraph"]
