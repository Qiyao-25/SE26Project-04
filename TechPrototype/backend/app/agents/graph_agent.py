"""Build an explainable knowledge graph for a parsed paper.

The graph stays deterministic and uses entities already extracted by the
summarizer. Related-paper edges are ranked by lexical overlap, so they are
presented as topic relations rather than invented citations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#-]{2,}|[0-9]{2,}|[\u4e00-\u9fff]{2,}")
STOPWORDS = {
    "about", "after", "based", "between", "from", "into", "over", "that", "than",
    "their", "there", "these", "this", "using", "with", "方法", "模型", "论文", "研究",
    "实验", "结果", "一种", "基于", "通过", "本文",
}
DATASET_HINTS = (
    "imagenet", "cifar", "coco", "glue", "superglue", "squad", "mnli", "wmt",
    "wikitext", "ms marco", "benchmark", "数据集",
)
RELATED_SCORE_THRESHOLD = 0.18
MAX_RELATED_PAPERS = 5
MAX_CONCEPTS = 6
MAX_METHODS = 5
MAX_DATASETS = 3


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


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in TOKEN_RE.findall(text or "")
        if token.casefold() not in STOPWORDS
    }


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip()).casefold()


def _clean_items(items: list[dict[str, Any]] | None, label_keys: tuple[str, ...]) -> list[dict[str, str]]:
    output = []
    seen: set[str] = set()
    for item in items or []:
        if isinstance(item, str) and item.strip():
            label = item.strip()
            description = label
        elif isinstance(item, dict):
            label = next((str(item.get(key) or "").strip() for key in label_keys if item.get(key)), "")
            if not label:
                continue
            description = str(item.get("description") or item.get("desc") or "").strip()
        else:
            continue
        key = _normalize_label(label)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append({"label": label, "description": description or label})
    return output


def _date_value(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _related_score(current_text: str, item: dict[str, Any], current_category: str) -> tuple[float, list[str]]:
    item_text = " ".join([
        str(item.get("title") or ""),
        str(item.get("abstract") or ""),
        str(item.get("primary_category") or ""),
        " ".join(str(author) for author in item.get("authors") or []),
    ])
    current_tokens = _tokens(current_text)
    item_tokens = _tokens(item_text)
    shared = sorted(current_tokens & item_tokens)
    union = current_tokens | item_tokens
    score = len(shared) / len(union) if union else 0.0
    if current_category and item.get("primary_category") == current_category:
        score += 0.2
    if current_tokens & _tokens(str(item.get("title") or "")):
        score += 0.15
    return min(score, 1.0), shared[:8]


class GraphAgent:
    def __init__(self, settings: Any) -> None:
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
        experiments: list[dict[str, Any]] | None = None,
        limitations: list[str] | None = None,
        related_papers: list[dict[str, Any]] | None = None,
    ) -> PaperGraph:
        paper_node = {
            "id": f"paper-{paper_id}",
            "type": "paper",
            "label": title or arxiv_id or f"Paper {paper_id}",
            "paperId": paper_id,
            "paper_id": paper_id,
            "arxiv_id": arxiv_id,
            "role": "current",
            "published_at": published_at,
            "lane": "current",
        }
        nodes = [paper_node]
        edges = []
        concept_items = _clean_items(concepts, ("name", "title", "label"))[:MAX_CONCEPTS]
        method_items = _clean_items(methods, ("title", "name", "label"))[:MAX_METHODS]
        experiment_items = _clean_items(experiments, ("title", "name", "label"))[:8]
        paper_text = " ".join([
            title,
            abstract,
            primary_category,
            *(item["label"] for item in concept_items),
            *(item["label"] for item in method_items),
        ])

        for index, item in enumerate(concept_items, 1):
            node_id = f"concept-{index}"
            nodes.append({
                "id": node_id,
                "type": "concept",
                "label": item["label"][:80],
                "description": item["description"][:240],
                "role": "concept",
                "lane": "concept",
            })
            edges.append({
                "id": f"edge-concept-{index}",
                "source": paper_node["id"],
                "target": node_id,
                "type": "introduces",
                "label": "提出/涉及",
                "tier": "primary",
                "weight": 1.0,
                "evidence": [item["label"][:80]],
            })

        for index, item in enumerate(method_items, 1):
            node_id = f"method-{index}"
            nodes.append({
                "id": node_id,
                "type": "method",
                "label": item["label"][:80],
                "description": item["description"][:240],
                "role": "method",
                "lane": "method",
            })
            edges.append({
                "id": f"edge-method-{index}",
                "source": paper_node["id"],
                "target": node_id,
                "type": "uses",
                "label": "使用方法",
                "tier": "primary",
                "weight": 1.0,
                "evidence": [item["label"][:80]],
            })

        dataset_seen: set[str] = set()
        dataset_count = 0
        for index, item in enumerate(experiment_items, 1):
            if dataset_count >= MAX_DATASETS:
                break
            experiment_text = f"{item['label']} {item['description']}".casefold()
            dataset = next((hint for hint in DATASET_HINTS if hint in experiment_text), None)
            if not dataset:
                continue
            key = _normalize_label(dataset)
            if key in dataset_seen:
                continue
            dataset_seen.add(key)
            dataset_count += 1
            node_id = f"dataset-{dataset_count}"
            nodes.append({
                "id": node_id,
                "type": "dataset",
                "label": dataset.upper() if dataset.isascii() else dataset,
                "description": item["description"][:240],
                "role": "dataset",
                "lane": "domain",
            })
            edges.append({
                "id": f"edge-dataset-{dataset_count}",
                "source": paper_node["id"],
                "target": node_id,
                "type": "evaluates_on",
                "label": "评测数据",
                "tier": "primary",
                "weight": 0.9,
                "evidence": [item["label"][:80]],
            })

        if primary_category:
            nodes.append({
                "id": "category-1",
                "type": "task",
                "label": primary_category,
                "role": "domain",
                "lane": "domain",
            })
            edges.append({
                "id": "edge-category",
                "source": paper_node["id"],
                "target": "category-1",
                "type": "in_domain",
                "label": "研究领域",
                "tier": "primary",
                "weight": 0.85,
                "evidence": [primary_category],
            })

        concept_nodes = [node for node in nodes if node["type"] == "concept"]
        for method_index, method in enumerate(method_items, 1):
            method_tokens = _tokens(f"{method['label']} {method['description']}")
            best = None
            for concept in concept_nodes:
                shared = sorted(method_tokens & _tokens(f"{concept['label']} {concept['description']}"))
                if not shared:
                    continue
                weight = min(0.85, 0.35 + 0.08 * len(shared))
                candidate = {
                    "id": f"edge-method-concept-{method_index}-{concept['id']}",
                    "source": f"method-{method_index}",
                    "target": concept["id"],
                    "type": "implements",
                    "label": "实现概念",
                    "tier": "secondary",
                    "weight": round(weight, 3),
                    "evidence": shared[:4],
                }
                if best is None or candidate["weight"] > best["weight"]:
                    best = candidate
            if best:
                edges.append(best)

        lineage = [{
            "paper_id": paper_id,
            "arxiv_id": arxiv_id,
            "title": title,
            "published_at": published_at,
            "role": "current",
            "note": "当前阅读论文",
        }]
        current_date = _date_value(published_at)
        scored_related = []
        for item in related_papers or []:
            if item.get("paper_id") == paper_id:
                continue
            score, shared = _related_score(paper_text, item, primary_category)
            if score < RELATED_SCORE_THRESHOLD:
                continue
            scored_related.append((score, shared, item))

        for index, (score, shared, item) in enumerate(
            sorted(scored_related, key=lambda value: value[0], reverse=True)[:MAX_RELATED_PAPERS], 1
        ):
            related_id = f"paper-{item.get('paper_id')}"
            related_date = _date_value(item.get("published_at"))
            if current_date and related_date and related_date < current_date:
                role, relation, label = "predecessor", "precedes", "可能的前置工作"
            elif current_date and related_date and related_date > current_date:
                role, relation, label = "successor", "follows", "可能的后续工作"
            else:
                role, relation, label = "related", "related_to", "主题相关"
            nodes.append({
                "id": related_id,
                "type": "paper",
                "label": item.get("title") or item.get("arxiv_id") or f"论文 {item.get('paper_id')}",
                "paperId": item.get("paper_id"),
                "paper_id": item.get("paper_id"),
                "arxiv_id": item.get("arxiv_id") or "",
                "published_at": item.get("published_at") or "",
                "role": role,
                "lane": "related",
                "description": f"相关度 {score:.2f}；匹配：{', '.join(shared) or '同领域'}",
                "score": round(score, 4),
            })
            lineage.append({
                "paper_id": item.get("paper_id"),
                "arxiv_id": item.get("arxiv_id") or "",
                "title": item.get("title") or "",
                "published_at": item.get("published_at") or "",
                "role": role,
                "note": f"{label}（匹配：{', '.join(shared) or '同领域'}）",
            })
            edges.append({
                "id": f"edge-related-{index}",
                "source": paper_node["id"],
                "target": related_id,
                "type": relation,
                "label": label,
                "tier": "primary" if score >= 0.35 else "secondary",
                "weight": round(score, 4),
                "evidence": shared,
            })

        focus = "、".join(item["label"] for item in concept_items[:3]) or "相关核心概念"
        limitations_note = "；存在待人工复核的局限性" if limitations else ""
        narrative = (
            f"当前论文围绕「{focus}」展开；图谱仅保留高相关关联论文（相关度≥{RELATED_SCORE_THRESHOLD}）"
            f"{limitations_note}。"
        )
        return PaperGraph(nodes=nodes, edges=edges, lineage=lineage, narrative=narrative)
