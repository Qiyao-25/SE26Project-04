"""Contract adapters: PaperPipeline ↔ backend API/ORM ↔ UIPrototype mocks.

Aligned with (2026-07 backend):
- POST /api/papers/batch  body = list[PaperUpsert]  (NOT wrapped in {"papers":...})
- AuthorInput: {name, orcid?}
- StructuredResult.result_type: summary | concepts | methods | limitations
- Wiki GET /api/papers/{id}/wiki reads those types
- QA POST /api/papers/{id}/qa  (AskPaperRequest)
- ApiResponse{code, message, data, request_id}
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any


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

# backend ingest_status → UI parseStatus (see service.papers.parse_status)
INGEST_TO_UI_PARSE: dict[str, str] = {
    "metadata_only": "pending",
    "downloaded": "pending",
    "parsed": "completed",
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


def ingest_status_to_ui_parse(ingest_status: str) -> str:
    return INGEST_TO_UI_PARSE.get(ingest_status, "pending")


def make_idempotency_key(arxiv_id: str, pipeline_ver: str = "v0") -> str:
    return hashlib.sha1(f"{arxiv_id}:{pipeline_ver}".encode("utf-8")).hexdigest()[:16]


def _authors_for_upsert(authors: list[Any]) -> list[dict[str, Any]]:
    """Map to backend AuthorInput {name, orcid?}."""
    out: list[dict[str, Any]] = []
    for a in authors or []:
        if isinstance(a, dict):
            name = a.get("name") or a.get("display_name") or ""
            if name:
                item: dict[str, Any] = {"name": name}
                if a.get("orcid"):
                    item["orcid"] = a["orcid"]
                out.append(item)
        elif isinstance(a, str) and a.strip():
            out.append({"name": a.strip()})
    return out


def paper_meta_to_backend(meta: Any) -> dict[str, Any]:
    """Map crawler PaperMeta → PaperUpsert dict for POST /api/papers/batch."""
    arxiv_id = re.sub(r"v\d+$", "", getattr(meta, "arxiv_id", "") or "")
    categories = getattr(meta, "categories", None) or []
    authors = getattr(meta, "authors", None) or []
    published = getattr(meta, "published", "") or ""
    return {
        "arxiv_id": arxiv_id,
        "title": getattr(meta, "title", "") or "",
        "abstract": getattr(meta, "abstract", None),
        "published_at": published or None,
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
    arxiv_id = re.sub(r"v\d+$", "", raw.get("arxiv_id", "") or "")
    categories = raw.get("categories") or []
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
            for item in (raw.get("authors") or [])
        ],
    }


def wiki_to_backend_structured_rows(
    *,
    summary: str,
    concept: str,
    methods: str,
    experiments: str = "",
    limitations: list[str] | None = None,
    validation_flags: list[str] | None = None,
    page_count: int = 0,
    source: str = "pipeline_extractive",
    version: int = 1,
) -> list[dict[str, Any]]:
    """Produce StructuredResult rows matching backend get_wiki() expectations.

    result_type values: summary | concepts | methods | experiments | limitations | validation
    content_json:
      - summary → {"summary": "..."}
      - concepts/methods/limitations → {"items": [...]}
    """
    locator = {"page_count": page_count, "source": source}
    rows: list[dict[str, Any]] = [
        {
            "result_type": "summary",
            "version": version,
            "content_json": {"summary": summary},
            "source_locator": locator,
            "confidence": None,
        }
    ]
    rows.extend(
        [
            {
                "result_type": "concepts",
                "version": version,
                "content_json": {
                    "items": [
                        {
                            "conceptId": "concept-core",
                            "name": "Core Concept",
                            "description": concept[:800],
                        }
                    ]
                    if concept
                    else [],
                },
                "source_locator": locator,
                "confidence": None,
            },
            {
                "result_type": "methods",
                "version": version,
                "content_json": {
                    "items": [
                        {
                            "order": 1,
                            "title": "Method Overview",
                            "description": methods[:800],
                        }
                    ]
                    if methods
                    else [],
                },
                "source_locator": locator,
                "confidence": None,
            },
            {
                "result_type": "experiments",
                "version": version,
                "content_json": {
                    "items": [
                        {
                            "title": "Experiments and Results",
                            "description": experiments[:800],
                        }
                    ]
                    if experiments
                    else [],
                },
                "source_locator": locator,
                "confidence": None,
            },
            {
                "result_type": "limitations",
                "version": version,
                "content_json": {"items": list(limitations or [])},
                "source_locator": locator,
                "confidence": None,
            },
            {
                "result_type": "validation",
                "version": version,
                "content_json": {"flags": list(validation_flags or [])},
                "source_locator": locator,
                "confidence": None,
            },
        ]
    )
    return rows


def wiki_to_backend_structured(
    *,
    summary: str,
    concept: str,
    methods: str,
    experiments: str = "",
    limitations: list[str] | None = None,
    validation_flags: list[str] | None = None,
    page_count: int = 0,
    source: str = "pipeline_extractive",
) -> dict[str, Any]:
    """Legacy single-blob helper; prefer wiki_to_backend_structured_rows for C write API."""
    return {
        "rows": wiki_to_backend_structured_rows(
            summary=summary,
            concept=concept,
            methods=methods,
            experiments=experiments,
            limitations=limitations,
            validation_flags=validation_flags,
            page_count=page_count,
            source=source,
        ),
        "note": "Backend wiki reads separate result_type rows, not a single wiki_triple.",
    }


def wiki_to_ui_summary(
    *,
    paper_id: str,
    arxiv_id: str,
    summary: str,
    concept: str,
    methods: str,
    experiments: str = "",
    limitations: list[str] | None = None,
    validation_flags: list[str] | None = None,
    parse_status: str = "completed",
) -> dict[str, Any]:
    """UIPrototype / backend PaperSummary-compatible shape."""
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
        "experiments": [{"title": "Experiments and Results", "description": experiments}] if experiments else [],
        "limitations": limitations or [],
        "validationFlags": validation_flags or [],
    }


def chunk_to_backend(chunk: dict[str, Any], *, paper_id_hint: str = "") -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id") or chunk.get("para_id") or "",
        "page_no": chunk.get("page_no", chunk.get("page")),
        "section": chunk.get("section"),
        "content": chunk.get("content") or chunk.get("text") or "",
    }


def paragraphs_to_text_chunks(paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Local parse paragraphs → TextChunk ORM rows (for future POST /api/papers/{id}/chunks)."""
    return [chunk_to_backend(p) for p in paragraphs]


def citation_to_ui(
    *,
    chunk_id: str,
    page_no: int | None,
    section: str | None,
    quote: str,
    paper_id: str | int,
    paper_title: str = "",
    index: int = 1,
) -> dict[str, Any]:
    section_title = section or "body"
    return {
        "citationId": f"citation-{index:03d}-{chunk_id}",
        "paperId": paper_id,
        "paperTitle": paper_title,
        "sectionId": f"section-{chunk_id}",
        "sectionTitle": section_title.replace("_", " ").title() if section_title else "原文",
        "pageNumber": page_no,
        "quote": (quote or "")[:400],
        "chunk_id": chunk_id,
        "page_no": page_no,
        "section": section,
    }


def qa_result_to_ui(
    *,
    arxiv_id: str,
    answer: str,
    citations: list[dict[str, Any]],
    paper_id: str | int | None = None,
    paper_title: str = "",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    pid = paper_id if paper_id is not None else arxiv_id
    ui_cites = [
        citation_to_ui(
            chunk_id=c.get("chunk_id", ""),
            page_no=c.get("page_no"),
            section=c.get("section"),
            quote=c.get("quote") or c.get("content") or "",
            paper_id=pid,
            paper_title=paper_title,
            index=i,
        )
        for i, c in enumerate(citations, start=1)
    ]
    return {
        "conversationId": conversation_id or f"conversation-{pid}",
        "messageId": f"assistant-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "paperId": pid,
        "answer": answer,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "citations": ui_cites,
    }


def unwrap_api_response(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload and ("code" in payload or "request_id" in payload):
        return payload["data"]
    return payload
