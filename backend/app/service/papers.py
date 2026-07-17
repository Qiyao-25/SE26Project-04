from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.agents.llm_client import LlmError
from app.agents.qa_agent import QaAgent
from app.model import Paper
from app.repository.chunks import search_chunks
from app.repository.papers import get_paper, list_papers, upsert_paper
from app.schema.papers import BatchUpsertResponse, ChunkSearchRequest, PaperItem, PaperPage, PaperUpsert, QaResponse, SmartSearchResponse, WikiData


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
        "queued": "queued",
        "parsing": "parsing",
        "parsed": "completed",
        "qa_ready": "qa_ready",
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
        chunk_count=paper.chunk_count,
        qa_ready=paper.ingest_status == "qa_ready" and paper.chunk_count > 0,
    )


def search_papers(session: Session, **filters) -> PaperPage:
    page = filters["page"]
    page_size = filters["page_size"]
    papers, total = list_papers(session, **filters)
    return PaperPage(items=[to_item(paper) for paper in papers], total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)


def smart_search_papers(
    session: Session,
    *,
    query: str,
    page: int = 1,
    page_size: int = 12,
    category: str | None = None,
    settings=None,
) -> SmartSearchResponse:
    from app.agents.search_agent import SearchAgent
    from app.core.config import get_settings

    settings = settings or get_settings()
    agent = SearchAgent(settings)
    plan = agent.plan(query)
    category_filter = category or (plan.category_hints[0] if plan.category_hints else None)
    papers, total = list_papers(
        session,
        keyword=plan.rewritten_query or query,
        keywords=plan.keywords or [query],
        author=None,
        category=category_filter,
        published_from=None,
        published_to=None,
        page=page,
        page_size=page_size,
    )
    if total == 0 and category_filter and not category:
        papers, total = list_papers(
            session,
            keyword=plan.rewritten_query or query,
            keywords=plan.keywords or [query],
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=page,
            page_size=page_size,
        )
    if total == 0 and plan.keywords:
        papers, total = list_papers(
            session,
            keyword=query,
            keywords=None,
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=page,
            page_size=page_size,
        )
    items = [to_item(paper) for paper in papers]
    paper_payload = [
        {
            "title": item.title,
            "authors": item.authors,
            "primary_category": item.primary_category,
            "abstract": item.abstract,
            "arxiv_id": item.arxiv_id,
        }
        for item in items
    ]
    answer = agent.answer(query=query, plan=plan, papers=paper_payload, total=total)
    return SmartSearchResponse(
        query=query,
        rewritten_query=plan.rewritten_query or query,
        keywords=plan.keywords,
        intent=plan.intent,
        answer=answer.answer,
        highlights=answer.highlights,
        plan_source=plan.source,
        answer_source=answer.source,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


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
    parsed = parse_status(paper) in {"completed", "qa_ready"}
    summary_content = summary.content_json.get("summary") if parsed and summary else (wiki.content_json.get("summary") if parsed and wiki else None)
    concept_content = concepts.content_json.get("items", []) if parsed and concepts else (wiki.content_json.get("concepts", wiki.content_json.get("concept", "")) if parsed and wiki else [])
    method_content = methods.content_json.get("items", []) if parsed and methods else (wiki.content_json.get("methods", "") if parsed and wiki else [])
    experiment_content = experiments.content_json.get("items", []) if parsed and experiments else []
    validation_flags = validation.content_json.get("flags", []) if parsed and validation else []
    if isinstance(concept_content, str):
        concept_content = [{"conceptId": f"{paper.id}-concept-1", "name": "Core Concept", "description": concept_content}]
    if isinstance(method_content, str):
        method_content = [{"order": 1, "title": "Method Overview", "description": method_content}]
    return WikiData(
        paper_id=paper.id,
        parse_status=parse_status(paper),
        summary=summary_content or "",
        concepts=concept_content,
        methods=method_content,
        experiments=experiment_content,
        limitations=(by_type.get("limitations").content_json.get("items", []) if parsed and by_type.get("limitations") else []),
        validation_flags=validation_flags,
        source_locator=(wiki.source_locator if parsed and wiki else (summary.source_locator if parsed and summary else {})),
        chunk_count=paper.chunk_count,
        qa_ready=paper.ingest_status == "qa_ready" and paper.chunk_count > 0,
    )


def answer_question(
    session: Session,
    paper_id: int,
    question: str,
    history: list[dict] | None = None,
    *,
    conversation_id: str | None = None,
    settings=None,
) -> QaResponse:
    from app.service.qa_citations import polish_quote, section_label, select_relevant_chunk_ids

    settings = settings or get_settings()
    paper = get_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)
    top_k = max(3, int(getattr(settings, "qa_agent_top_k", 3)))
    matches = search_chunks(session, ChunkSearchRequest(query=question, paper_id=paper_id, top_k=top_k))
    if not matches:
        raise PaperServiceError("NO_EVIDENCE", "当前论文没有可核验的原文依据，请先完成文本块解析后再提问", 422)

    evidence = [
        {
            "chunk_id": chunk.chunk_id,
            "page_no": chunk.page_no,
            "section": chunk.section,
            "content": chunk.content,
        }
        for chunk, _score in matches
    ]
    chunk_by_id = {chunk.chunk_id: chunk for chunk, _score in matches}
    history_payload = [
        {"role": str(item.get("role") or ""), "content": str(item.get("content") or "")}
        for item in (history or [])
        if isinstance(item, dict) and item.get("role") and item.get("content")
    ]

    if settings.qa_agent_ready:
        try:
            generated = QaAgent(settings).run(
                title=paper.title or "",
                question=question,
                evidence=evidence,
                history=history_payload,
            )
        except LlmError as exc:
            raise PaperServiceError("QA_AGENT_FAILED", f"问答生成失败：{exc}", 502) from exc
        if generated.refuse and not generated.citation_ids:
            raise PaperServiceError("NO_EVIDENCE", generated.answer or "依据不足，无法回答该问题", 422)
        answer = generated.answer
        selected_ids = select_relevant_chunk_ids(
            answer=answer,
            evidence=evidence,
            preferred_ids=generated.citation_ids,
            min_overlap=0.06,
            max_citations=3,
        )
    else:
        answer = "基于当前论文解析结果：\n" + "\n".join(
            polish_quote(item["content"], answer=question, max_len=220)
            for item in evidence[:3]
        )
        selected_ids = select_relevant_chunk_ids(
            answer=question,
            evidence=evidence,
            preferred_ids=[item["chunk_id"] for item in evidence],
            min_overlap=0.02,
            max_citations=3,
        )

    citations = []
    for chunk_id in selected_ids:
        chunk = chunk_by_id.get(chunk_id)
        if chunk is None:
            continue
        quote = polish_quote(chunk.content or "", answer=answer, max_len=280)
        if quote:
            citations.append(
                {
                    "citationId": f"citation-{paper.id}-{chunk.chunk_id}",
                    "paperId": paper.id,
                    "paperTitle": paper.title,
                    "sectionId": chunk.chunk_id,
                    "sectionTitle": section_label(chunk.section, chunk.content or ""),
                    "pageNumber": chunk.page_no,
                    "quote": quote,
                }
            )
    if not answer.strip():
        raise PaperServiceError("NO_EVIDENCE", "当前论文没有可核验的原文依据，请先完成文本块解析后再提问", 422)

    return QaResponse(
        conversation_id=conversation_id or f"conversation-{paper.id}",
        message_id=f"assistant-{uuid4()}",
        paper_id=paper.id,
        answer=answer,
        created_at=datetime.now(timezone.utc),
        citations=citations,
    )
