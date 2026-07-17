from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.model import Paper
from app.repository.chunks import search_chunks
from app.repository.papers import get_paper, list_papers, upsert_paper
from app.schema.papers import BatchUpsertResponse, ChunkSearchRequest, PaperItem, PaperPage, PaperUpsert, QaResponse, WikiData


class PaperServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message


def parse_status(paper: Paper) -> str:
    return {
        "metadata_only": "pending",
        "downloaded": "pending",
        "parsed": "completed",
        "failed": "failed",
    }.get(paper.ingest_status, "pending")


def to_item(paper: Paper) -> PaperItem:
    authors = [link.author.display_name for link in sorted(paper.authors, key=lambda link: link.author_order)]
    return PaperItem(
        paper_id=paper.id,
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=authors,
        abstract=paper.abstract,
        published_at=paper.published_at,
        primary_category=paper.primary_category,
        pdf_url=paper.pdf_url,
        source_url=paper.source_url,
        ingest_status=paper.ingest_status,
        parse_status=parse_status(paper),
    )


def search_papers(session: Session, **filters) -> PaperPage:
    page = filters["page"]
    page_size = filters["page_size"]
    papers, total = list_papers(session, **filters)
    return PaperPage(items=[to_item(paper) for paper in papers], total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)


def batch_upsert_papers(session: Session, payloads: list[PaperUpsert]) -> BatchUpsertResponse:
    created = 0
    updated = 0
    papers: list[Paper] = []
    try:
        for payload in payloads:
            paper, was_created = upsert_paper(session, payload)
            papers.append(paper)
            if was_created:
                created += 1
            else:
                updated += 1
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise PaperServiceError("PAPER_CONFLICT", "论文或作者的业务标识已存在", 409) from exc
    return BatchUpsertResponse(items=[to_item(paper) for paper in papers], created=created, updated=updated)


def get_paper_detail(session: Session, paper_id: int) -> PaperItem:
    paper = get_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)
    return to_item(paper)


def get_wiki(session: Session, paper_id: int) -> WikiData:
    paper = get_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)

    results = sorted(paper.structured_results, key=lambda result: (result.result_type, -result.version))
    by_type = {}
    for result in results:
        by_type.setdefault(result.result_type, result)
    wiki = by_type.get("wiki_triple")
    summary = by_type.get("summary")
    concepts = by_type.get("concepts")
    methods = by_type.get("methods")
    experiments = by_type.get("experiments")
    validation = by_type.get("validation")
    summary_content = summary.content_json.get("summary") if summary else (wiki.content_json.get("summary") if wiki else None)
    concept_content = concepts.content_json.get("items", []) if concepts else (wiki.content_json.get("concepts", wiki.content_json.get("concept", "")) if wiki else [])
    method_content = methods.content_json.get("items", []) if methods else (wiki.content_json.get("methods", "") if wiki else [])
    experiment_content = experiments.content_json.get("items", []) if experiments else []
    validation_flags = validation.content_json.get("flags", []) if validation else []
    if isinstance(concept_content, str):
        concept_content = [{"conceptId": f"{paper.id}-concept-1", "name": "Core Concept", "description": concept_content}]
    if isinstance(method_content, str):
        method_content = [{"order": 1, "title": "Method Overview", "description": method_content}]
    return WikiData(
        paper_id=paper.id,
        parse_status=parse_status(paper),
        summary=summary_content or paper.abstract,
        concepts=concept_content,
        methods=method_content,
        experiments=experiment_content,
        limitations=(by_type.get("limitations").content_json.get("items", []) if by_type.get("limitations") else []),
        validation_flags=validation_flags,
        source_locator=(wiki.source_locator if wiki else (summary.source_locator if summary else {})),
    )


def answer_question(session: Session, paper_id: int, question: str) -> QaResponse:
    paper = get_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)
    matches = search_chunks(session, ChunkSearchRequest(query=question, paper_id=paper_id, top_k=3))
    if matches:
        excerpts = [chunk.content[:500] for chunk, _score in matches]
        citations = [
            {
                "citationId": f"citation-{paper.id}-{chunk.chunk_id}",
                "paperId": paper.id,
                "paperTitle": paper.title,
                "sectionId": chunk.chunk_id,
                "sectionTitle": chunk.section or "原文",
                "pageNumber": chunk.page_no,
                "quote": chunk.content[:500],
            }
            for chunk, _score in matches
        ]
        answer = "\n".join(excerpts)
    else:
        raise PaperServiceError("NO_EVIDENCE", "当前论文没有可核验的原文依据，请先完成文本块解析后再提问", 422)
    return QaResponse(
        conversation_id=f"conversation-{paper.id}",
        message_id=f"assistant-{uuid4()}",
        paper_id=paper.id,
        answer=f"基于当前论文解析结果，关于“{question}”：{answer}",
        created_at=datetime.now(timezone.utc),
        citations=citations,
    )
