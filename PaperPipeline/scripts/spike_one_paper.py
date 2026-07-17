#!/usr/bin/env python3
"""H017/H018 Spike: arXiv fetch → PDF parse → extractive summarize."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
# PaperPipeline/scripts → ROOT=PaperPipeline, data/spike/; PaperPipeline/src/pipeline → ROOT=PaperPipeline, data/spike/
_HERE = Path(__file__).resolve().parent
if _HERE.name == "scripts":
    ROOT = _HERE.parent
    DATA_DIR = ROOT / "data" / "spike"
else:
    ROOT = _HERE.parents[1]
    DATA_DIR = ROOT / "data" / "spike"
PDF_DIR = DATA_DIR / "pdfs"
OUT_DIR = DATA_DIR / "runs"


@dataclass
class PaperMeta:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    pdf_url: str
    abs_url: str


@dataclass
class StageResult:
    stage: str
    status: str
    elapsed_s: float
    detail: str = ""


def _http_get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PaperMate-Spike/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def search_by_keyword(keyword: str, max_results: int = 1) -> list[PaperMeta]:
    query = urllib.parse.urlencode(
        {"search_query": f"all:{keyword}", "start": 0, "max_results": max_results}
    )
    xml_bytes = _http_get(f"{ARXIV_API}?{query}", timeout=10)
    root = ET.fromstring(xml_bytes)
    papers: list[PaperMeta] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        raw_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        arxiv_id = raw_id.rsplit("/abs/", 1)[-1]
        title = re.sub(r"\s+", " ", entry.findtext("atom:title", default="", namespaces=ATOM_NS)).strip()
        abstract = re.sub(r"\s+", " ", entry.findtext("atom:summary", default="", namespaces=ATOM_NS)).strip()
        authors = [
            a.findtext("atom:name", default="", namespaces=ATOM_NS)
            for a in entry.findall("atom:author", ATOM_NS)
        ]
        categories = [c.get("term", "") for c in entry.findall("atom:category", ATOM_NS)]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        papers.append(
            PaperMeta(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                categories=categories,
                pdf_url=pdf_url,
                abs_url=abs_url,
            )
        )
    return papers


def fetch_by_id(arxiv_id: str) -> PaperMeta:
    papers = search_by_keyword(arxiv_id.replace(".", " "), max_results=5)
    for p in papers:
        if p.arxiv_id == arxiv_id:
            return p
    # fallback: id_list query
    query = urllib.parse.urlencode({"id_list": arxiv_id})
    xml_bytes = _http_get(f"{ARXIV_API}?{query}", timeout=10)
    root = ET.fromstring(xml_bytes)
    entry = root.find("atom:entry", ATOM_NS)
    if entry is None:
        raise ValueError(f"arXiv ID not found: {arxiv_id}")
    raw_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
    aid = raw_id.rsplit("/abs/", 1)[-1]
    return PaperMeta(
        arxiv_id=aid,
        title=re.sub(r"\s+", " ", entry.findtext("atom:title", default="", namespaces=ATOM_NS)).strip(),
        authors=[
            a.findtext("atom:name", default="", namespaces=ATOM_NS)
            for a in entry.findall("atom:author", ATOM_NS)
        ],
        abstract=re.sub(r"\s+", " ", entry.findtext("atom:summary", default="", namespaces=ATOM_NS)).strip(),
        categories=[c.get("term", "") for c in entry.findall("atom:category", ATOM_NS)],
        pdf_url=f"https://arxiv.org/pdf/{aid}.pdf",
        abs_url=f"https://arxiv.org/abs/{aid}",
    )


def download_pdf(meta: PaperMeta, timeout: float = 60.0) -> Path:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / f"{meta.arxiv_id.replace('/', '_')}.pdf"
    if dest.exists() and dest.stat().st_size > 1024:
        return dest
    data = _http_get(meta.pdf_url, timeout=timeout)
    if not data.startswith(b"%PDF"):
        raise ValueError("Downloaded file is not a PDF")
    dest.write_bytes(data)
    return dest


def extract_text(pdf_path: Path, max_pages: int | None = None) -> tuple[str, int]:
    reader = PdfReader(str(pdf_path))
    pages = reader.pages[: max_pages or len(reader.pages)]
    chunks: list[str] = []
    for page in pages:
        text = page.extract_text() or ""
        chunks.append(text)
    full = "\n".join(chunks)
    full = re.sub(r"\n{3,}", "\n\n", full)
    return full.strip(), len(reader.pages)


def _top_sentences(text: str, limit: int = 3) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored: list[tuple[int, str]] = []
    for s in sentences:
        s = s.strip()
        if len(s) < 40 or len(s) > 400:
            continue
        score = len(re.findall(r"\b(model|attention|transformer|method|propose|learn)\b", s, re.I))
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [s for _, s in scored[:limit]]
    return picked or sentences[:limit]


def summarize_extractive(meta: PaperMeta, body: str) -> dict[str, str]:
    intro = body[:8000]
    summary_bits = [meta.abstract] + _top_sentences(intro, limit=2)
    summary = " ".join(summary_bits)[:1200]

    concept_hits = _top_sentences(intro, limit=4)
    concept = " ".join(concept_hits)[:900]

    methods_match = re.search(
        r"(?is)(method|approach|architecture|model).{0,40}\n(.{200,1200})",
        body[:20000],
    )
    if methods_match:
        methods = re.sub(r"\s+", " ", methods_match.group(0))[:900]
    else:
        methods = " ".join(_top_sentences(body[2000:12000], limit=3))[:900]

    return {
        "summary": summary.strip(),
        "concept": concept.strip(),
        "methods": methods.strip(),
    }


def run_stage(name: str, fn) -> tuple[object | None, StageResult]:
    t0 = time.perf_counter()
    try:
        result = fn()
        elapsed = time.perf_counter() - t0
        return result, StageResult(stage=name, status="ok", elapsed_s=round(elapsed, 2))
    except Exception as exc:  # noqa: BLE001 - spike script keeps going
        elapsed = time.perf_counter() - t0
        return None, StageResult(stage=name, status="failed", elapsed_s=round(elapsed, 2), detail=str(exc))


def to_backend_paper(meta: PaperMeta) -> dict:
    """Map spike PaperMeta → backend Paper ORM fields (entities.Paper)."""
    base_id = re.sub(r"v\d+$", "", meta.arxiv_id)
    primary = meta.categories[0] if meta.categories else None
    return {
        "arxiv_id": base_id,
        "title": meta.title,
        "abstract": meta.abstract,
        "published_at": None,
        "primary_category": primary,
        "pdf_url": f"https://arxiv.org/pdf/{base_id}.pdf",
        "source_url": f"https://arxiv.org/abs/{base_id}",
        "ingest_status": "metadata_only",
        "authors": [{"name": a} for i, a in enumerate(meta.authors)],
    }


def _idem_key(arxiv_id: str, pipeline_ver: str = "v0") -> str:
    return hashlib.sha1(f"{arxiv_id}:{pipeline_ver}".encode()).hexdigest()[:16]


def to_backend_payload(
    meta: PaperMeta | None,
    pdf_path: Path | str | None,
    structured: dict | None,
    *,
    page_count: int = 0,
    status: str = "qa_ready",
) -> dict | None:
    """Shape for future upsert into ParseTask / PaperContent / StructuredResult / TextChunk."""
    if not meta:
        return None
    paper = to_backend_paper(meta)
    if status in {"summarized", "qa_ready", "parsed"}:
        paper["ingest_status"] = "qa_ready" if status == "qa_ready" else status
    orm_status = "succeeded" if structured else "failed"
    return {
        "parse_task": {
            "task_type": "full_pipeline",
            "status": orm_status,
            "attempt": 1,
            "idempotency_key": _idem_key(paper["arxiv_id"]),
            "error_code": None if structured else "summarize_failed",
        },
        "paper": paper,
        "paper_content": {
            "storage_path": str(pdf_path) if pdf_path else None,
            "mime_type": "application/pdf",
            "checksum": None,
        },
        "structured_result": {
            "result_type": "wiki_triple",
            "version": 1,
            "content_json": structured or {},
            "source_locator": {"page_count": page_count, "source": "spike_extractive"},
        },
        "ui_summary": {
            "paperId": paper["arxiv_id"],
            "parseStatus": "completed" if structured else "failed",
            "summary": (structured or {}).get("summary", ""),
            "concepts": [
                {
                    "conceptId": f"concept-{paper['arxiv_id']}-0",
                    "name": "Core Concept",
                    "description": (structured or {}).get("concept", "")[:500],
                }
            ]
            if structured and structured.get("concept")
            else [],
            "methods": [
                {
                    "order": 1,
                    "title": "Method Overview",
                    "description": (structured or {}).get("methods", "")[:500],
                }
            ]
            if structured and structured.get("methods")
            else [],
            "limitations": [],
        },
        "api_note": "Backend currently exposes GET /health only; upsert routes pending member C.",
    }


def cmd_fetch(keyword: str) -> int:
    meta, stage = run_stage("fetch_metadata", lambda: search_by_keyword(keyword, max_results=1)[0])
    payload = {
        "task": "H017",
        "keyword": keyword,
        "stages": [asdict(stage)],
        "paper": asdict(meta) if meta else None,
        "backend_paper": to_backend_paper(meta) if meta else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0 if meta else 1


def cmd_pipeline(arxiv_id: str, keyword: str | None) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stages: list[StageResult] = []
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if arxiv_id:
        meta, s = run_stage("fetch_metadata", lambda: fetch_by_id(arxiv_id))
    else:
        meta, s = run_stage("fetch_metadata", lambda: search_by_keyword(keyword or "attention transformer", 1)[0])
    stages.append(s)
    if not meta:
        _save_run(run_id, None, stages, None, None, None)
        return 1

    pdf_path, s = run_stage("download_pdf", lambda: download_pdf(meta))
    stages.append(s)
    if not pdf_path:
        _save_run(run_id, meta, stages, None, None, None)
        return 1

    parsed, s = run_stage("parse_pdf", lambda: extract_text(pdf_path))
    stages.append(s)
    if not parsed:
        _save_run(run_id, meta, stages, str(pdf_path), None, None)
        return 1

    body, page_count = parsed
    summary, s = run_stage("summarize", lambda: summarize_extractive(meta, body))
    stages.append(s)

    status = "summarized" if summary and all(summary.values()) else "summarize_failed"
    spike_status = "qa_ready" if status == "summarized" else status
    backend = to_backend_payload(
        meta, pdf_path, summary, page_count=page_count, status=spike_status
    )
    output = {
        "task": "H017+H018",
        "run_id": run_id,
        "sample": "P1" if meta.arxiv_id.startswith("1706.03762") else meta.arxiv_id,
        "paper": asdict(meta),
        "pdf_path": str(pdf_path),
        "page_count": page_count,
        "body_chars": len(body),
        "body_preview": body[:500],
        "structured": summary if summary else None,
        "backend_upsert": backend,
        "stages": [asdict(x) for x in stages],
        "status": status,
    }
    out_file = _save_run(run_id, meta, stages, str(pdf_path), body, summary, backend)
    output["artifact"] = str(out_file)
    print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)
    return 0 if output["status"] == "summarized" else 1


def _save_run(run_id, meta, stages, pdf_path, body, structured, backend=None) -> Path:
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paper": asdict(meta) if meta else None,
        "pdf_path": pdf_path,
        "body_chars": len(body) if body else 0,
        "structured": structured,
        "backend_upsert": backend,
        "stages": [asdict(x) for x in stages],
    }
    out_file = OUT_DIR / f"run_{run_id}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperMate arXiv spike (H017/H018)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="H017: keyword search, return 1 paper metadata")
    p_fetch.add_argument("--keyword", default="attention is all you need", help="arXiv search keyword")

    p_pipe = sub.add_parser("pipeline", help="H017+H018: fetch → download → parse → summarize")
    p_pipe.add_argument("--arxiv-id", default="1706.03762", help="Frozen sample ID (default P1)")
    p_pipe.add_argument("--keyword", default=None, help="Use keyword search instead of fixed ID")

    args = parser.parse_args()
    if args.command == "fetch":
        return cmd_fetch(args.keyword)
    if args.command == "pipeline":
        return cmd_pipeline(args.arxiv_id, args.keyword)
    return 1


if __name__ == "__main__":
    sys.exit(main())
