"""Build a small, deterministic knowledge graph for a parsed paper."""

from dataclasses import dataclass, field
from typing import Any


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
                "confidence": 0.55,
            },
            {
                "result_type": "topic_lineage",
                "version": 1,
                "content_json": {"items": self.lineage, "narrative": self.narrative, "source": self.source},
                "source_locator": locator,
                "confidence": 0.5,
            },
        ]


class GraphAgent:
    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def run(self, *, paper_id: int, title: str, abstract: str, arxiv_id: str = "", primary_category: str = "", published_at: str = "", concepts: list[dict[str, Any]] | None = None, methods: list[dict[str, Any]] | None = None, related_papers: list[dict[str, Any]] | None = None) -> PaperGraph:
        paper_node = {
            "id": f"paper-{paper_id}",
            "type": "paper",
            "label": title or arxiv_id or f"Paper {paper_id}",
            "paper_id": paper_id,
            "arxiv_id": arxiv_id,
            "role": "current",
            "published_at": published_at,
        }
        nodes = [paper_node]
        edges = []
        for index, item in enumerate((concepts or [])[:6], 1):
            node_id = f"concept-{index}"
            nodes.append({"id": node_id, "type": "concept", "label": str(item.get("name") or f"概念{index}"), "description": str(item.get("description") or "")[:200]})
            edges.append({"id": f"edge-concept-{index}", "source": paper_node["id"], "target": node_id, "type": "introduces", "label": "提出/涉及"})
        for index, item in enumerate((methods or [])[:5], 1):
            node_id = f"method-{index}"
            nodes.append({"id": node_id, "type": "method", "label": str(item.get("title") or item.get("name") or f"方法{index}"), "description": str(item.get("description") or "")[:200]})
            edges.append({"id": f"edge-method-{index}", "source": paper_node["id"], "target": node_id, "type": "uses", "label": "使用方法"})
        if primary_category:
            nodes.append({"id": "category-1", "type": "task", "label": primary_category})
            edges.append({"id": "edge-category", "source": paper_node["id"], "target": "category-1", "type": "related_to", "label": "领域"})
        lineage = [{"paper_id": paper_id, "arxiv_id": arxiv_id, "title": title, "published_at": published_at, "role": "current", "note": "当前阅读论文"}]
        for item in (related_papers or [])[:8]:
            if item.get("paper_id") == paper_id:
                continue
            lineage.append({"paper_id": item.get("paper_id"), "arxiv_id": item.get("arxiv_id") or "", "title": item.get("title") or "", "published_at": item.get("published_at") or "", "role": "related", "note": "库内主题相近论文"})
        concept_names = [str(item.get("name")) for item in (concepts or [])[:3] if item.get("name")]
        focus = "、".join(concept_names) or "相关核心概念"
        narrative = f"围绕《{title}》，图谱聚焦 {focus}。当前匹配到 {max(0, len(lineage) - 1)} 篇主题相近论文，关系边由解析结果生成。"
        return PaperGraph(nodes=nodes, edges=edges, lineage=lineage, narrative=narrative)


__all__ = ["GraphAgent", "PaperGraph"]
