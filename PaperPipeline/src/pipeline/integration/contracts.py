"""Contract adapters: PaperPipeline ↔ backend ORM ↔ UIPrototype mocks.

References:
- backend/app/model/entities.py
- backend/app/schema/common.py (ApiResponse: code/message/data/request_id)
- UIPrototype/frontend/src/mocks/paper-*.json
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# ParseTask status: pipeline-granular ↔ ORM-coarse
# ---------------------------------------------------------------------------

PIPELINE_TO_ORM_STATUS: dict[str, str] = {
    "pending": "queued",
    "fetching": "running",
    "fetched": "running",
    "parsing": "running",
    "parsed": "running",
    "parsed_degraded": "running",
    "summarizing": "running",
    "summarized": "succeeded",
    "qa_ready": "succeeded",
    "fetch_failed": "failed",
    "parse_failed": "failed",
    "parse_timeout": "failed",
    "summarize_failed": "failed",
    "failed": "failed",
}

ORM_TO_UI_PARSE_STATUS: dict[str, str] = {
    "queued": "pending",
    "running": "parsing",
    "succeeded": "completed",
    "failed": "failed",
}


def pipeline_status_to_orm(status: str) -> str:
    return PIPELINE_TO_ORM_STATUS.get(status, "queued")


def orm_status_to_ui_parse(status: str) -> str:
    return ORM_TO_UI_PARSE_STATUS.get(status, "pending")


def make_idempotency_key(arxiv_id: str, pipeline_ver: str = "v0") -> str:
    raw = f"{arxiv_id}:{pipeline_ver}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# PaperMeta → backend Paper ORM (entities.Paper + authors)
# ---------------------------------------------------------------------------

def paper_meta_to_backend(meta: Any) -> dict[str, Any]:
    """Map crawler PaperMeta → POST /papers/batch item (ORM-aligned)."""
    arxiv_id = re.sub(r"v\d+$", "", getattr(meta, "arxiv_id", "") or "")
    categories = getattr(meta, "categories", None) or []
    authors = getattr(meta, "authors", None) or []
    published = getattr(meta, "published", "") or ""
    published_at = published if published else None
    return {
        "arxiv_id": arxiv_id,
        "title": getattr(meta, "title", "") or "",
        "abstract": getattr(meta, "abstract", None),
        "published_at": published_at,
        "primary_category": categories[0] if categories else None,
        "pdf_url": getattr(meta, "pdf_url", None) or f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        "source_url": getattr(meta, "abs_url", None) or f"https://arxiv.org/abs/{arxiv_id}",
        "ingest_status": "metadata_only",
        "authors": [
            {"name": name}
            for i, name in enumerate(authors)
            if name
        ],
    }


def paper_dict_to_backend(raw: dict[str, Any]) -> dict[str, Any]:
    """Same mapping when input is already a dict (seed.json rows)."""
    arxiv_id = re.sub(r"v\d+$", "", raw.get("arxiv_id", "") or "")
    categories = raw.get("categories") or []
    authors = raw.get("authors") or []
    return {
        "arxiv_id": arxiv_id,
        "title": raw.get("title") or "",
        "abstract": raw.get("abstract"),
        "published_at": raw.get("published") or raw.get("published_at"),
        "primary_category": categories[0] if categories else raw.get("primary_category"),
        "pdf_url": raw.get("pdf_url") or f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        "source_url": raw.get("abs_url") or raw.get("source_url") or f"https://arxiv.org/abs/{arxiv_id}",
        "ingest_status": raw.get("ingest_status") or "metadata_only",
        "authors": [
            {"name": item.get("name") or item.get("display_name")}
            if isinstance(item, dict)
            else {"name": item}
            for item in authors
        ],
    }


# ---------------------------------------------------------------------------
# Structured wiki → backend StructuredResult + UI paper-summary
# ---------------------------------------------------------------------------

def wiki_to_backend_structured(
    *,
    summary: str,
    concept: str,
    methods: str,
    page_count: int = 0,
    source: str = "pipeline_extractive",
) -> dict[str, Any]:
    """ORM StructuredResult row shape (content_json + source_locator)."""
    return {
        "result_type": "wiki_triple",
        "version": 1,
        "content_json": {
            "summary": summary,
            "concept": concept,
            "methods": methods,
        },
        "source_locator": {"page_count": page_count, "source": source},
        "confidence": None,
    }


def wiki_to_ui_summary(
    *,
    paper_id: str,
    arxiv_id: str,
    summary: str,
    concept: str,
    methods: str,
    parse_status: str = "completed",
) -> dict[str, Any]:
    """UIPrototype paper-summary.json `data` shape."""
    concepts = []
    if concept:
        concepts.append(
            {
                "conceptId": f"concept-{arxiv_id}-0",
                "name": "Core Concept",
                "description": concept[:500],
            }
        )
    method_items = []
    if methods:
        method_items.append(
            {
                "order": 1,
                "title": "Method Overview",
                "description": methods[:500],
            }
        )
    return {
        "paperId": paper_id or arxiv_id,
        "parseStatus": parse_status,
        "summary": summary,
        "concepts": concepts,
        "methods": method_items,
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# TextChunk / QA citations → UI citation cards
# ---------------------------------------------------------------------------

def chunk_to_backend(chunk: dict[str, Any], *, paper_id_hint: str = "") -> dict[str, Any]:
    """Normalize local para / remote chunk → TextChunk ORM fields."""
    return {
        "chunk_id": chunk.get("chunk_id") or chunk.get("para_id") or "",
        "page_no": chunk.get("page_no", chunk.get("page")),
        "section": chunk.get("section"),
        "content": chunk.get("content") or chunk.get("text") or "",
    }


def citation_to_ui(
    *,
    chunk_id: str,
    page_no: int | None,
    section: str | None,
    quote: str,
    paper_id: str,
    paper_title: str = "",
    index: int = 1,
) -> dict[str, Any]:
    """UIPrototype paper-qa.json citation card (ChatPanel fields)."""
    section_title = section or "body"
    return {
        "citationId": f"citation-{index:03d}-{chunk_id}",
        "paperId": paper_id,
        "paperTitle": paper_title,
        "sectionId": f"section-{chunk_id}",
        "sectionTitle": section_title.replace("_", " ").title() if section_title else "原文",
        "pageNumber": page_no,
        "quote": (quote or "")[:400],
        # Backend / pipeline dual fields (for C API / PaperPipeline eval)
        "chunk_id": chunk_id,
        "page_no": page_no,
        "section": section,
    }


def qa_result_to_ui(
    *,
    arxiv_id: str,
    answer: str,
    citations: list[dict[str, Any]],
    paper_id: str | None = None,
    paper_title: str = "",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """UIPrototype askPaper response `data` shape."""
    pid = paper_id or arxiv_id
    ui_cites = []
    for i, c in enumerate(citations, start=1):
        ui_cites.append(
            citation_to_ui(
                chunk_id=c.get("chunk_id", ""),
                page_no=c.get("page_no"),
                section=c.get("section"),
                quote=c.get("quote") or c.get("content") or "",
                paper_id=pid,
                paper_title=paper_title,
                index=i,
            )
        )
    return {
        "conversationId": conversation_id or f"conversation-{pid}",
        "messageId": f"assistant-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "paperId": pid,
        "answer": answer,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "citations": ui_cites,
    }


def unwrap_api_response(payload: Any) -> Any:
    """Accept backend ApiResponse{code,message,data,request_id} or bare data."""
    if isinstance(payload, dict) and "data" in payload and ("code" in payload or "request_id" in payload):
        return payload["data"]
    return payload
