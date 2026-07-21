from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.agents.llm_client import LlmError
from app.agents.qa_agent import QaAgent
from app.agents.graph_agent import GraphAgent
from app.model import Paper, StructuredResult
from app.repository.chunks import search_chunks
from app.repository.papers import get_paper, list_papers, soft_delete_paper, upsert_paper
from app.schema.papers import BatchUpsertResponse, ChunkSearchRequest, GraphEdge, GraphNode, LineageItem, PaperGraphData, PaperItem, PaperPage, PaperUpsert, QaResponse, ReadingAssistData, ReadingAssistSection, SmartSearchResponse, WikiData

class PaperServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message


MIN_QA_RETRIEVAL_SCORE = 0.08


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


def delete_paper(session: Session, paper_id: int) -> PaperItem:
    paper = soft_delete_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", f"论文不存在：{paper_id}", 404)
    return to_item(paper)


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
    uncertain_fields = validation.content_json.get("uncertain_fields", []) if parsed and validation else []
    from app.service.content_validator import flag_labels

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
        validation_labels=flag_labels(validation_flags),
        uncertain_fields=list(uncertain_fields or []),
        source_locator=(wiki.source_locator if parsed and wiki else (summary.source_locator if parsed and summary else {})),
        chunk_count=paper.chunk_count,
        qa_ready=paper.ingest_status == "qa_ready" and paper.chunk_count > 0,
    )


def get_reading_assist(session: Session, paper_id: int, *, mode: str = "研究", force: bool = False, settings=None) -> ReadingAssistData:
    """Mode-specific reading guidance via ReadingModeAgent (LLM) with heuristic fallback."""
    from app.agents.llm_client import LlmError
    from app.agents.reading_mode_agent import PERSONAS, ReadingModeAgent, build_fallback_assist
    from app.core.config import get_settings

    paper = get_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)
    persona = mode if mode in PERSONAS else "研究"
    settings = settings or get_settings()
    wiki = get_wiki(session, paper_id)

    if not force:
        cached = _load_cached_reading_assist(session, paper, persona)
        if cached is not None:
            return cached

    agent_result = None
    if settings.assist_agent_ready:
        try:
            agent_result = ReadingModeAgent(settings).run(
                mode=persona,
                title=paper.title or "",
                abstract=paper.abstract or "",
                summary=wiki.summary or "",
                concepts=wiki.concepts,
                methods=wiki.methods,
                experiments=wiki.experiments,
                limitations=wiki.limitations,
                primary_category=paper.primary_category or "",
                arxiv_id=paper.arxiv_id or "",
            )
        except (LlmError, Exception) as exc:  # noqa: BLE001
            logger.warning("reading_mode_agent_fallback paper_id=%s mode=%s err=%s", paper_id, persona, exc)
            agent_result = None

    if agent_result is None:
        agent_result = build_fallback_assist(
            mode=persona,
            title=paper.title or "",
            summary=wiki.summary or "",
            abstract=paper.abstract or "",
            concepts=wiki.concepts,
            methods=wiki.methods,
            limitations=wiki.limitations,
        )

    data = ReadingAssistData(
        paper_id=paper.id,
        mode=persona,
        headline=agent_result.headline,
        sections=[ReadingAssistSection(title=str(s.get("title") or ""), bullets=[str(b) for b in (s.get("bullets") or [])[:6]]) for s in agent_result.sections if isinstance(s, dict)],
        takeaways=list(agent_result.takeaways or [])[:5],
        next_steps=list(agent_result.next_steps or [])[:4],
        source=agent_result.source,
        generated=agent_result.source != "heuristic",
    )
    _persist_reading_assist(session, paper, data)
    return data


def _load_cached_reading_assist(session: Session, paper: Paper, mode: str) -> ReadingAssistData | None:
    result = max(
        (
            item
            for item in paper.structured_results
            if item.result_type == "reading_assist" and isinstance(item.content_json, dict) and item.content_json.get("mode") == mode
        ),
        key=lambda item: item.version,
        default=None,
    )
    if result is None or not isinstance(result.content_json, dict):
        return None
    content = result.content_json
    sections_raw = content.get("sections") or []
    sections = [
        ReadingAssistSection(title=str(item.get("title") or ""), bullets=[str(b) for b in (item.get("bullets") or [])[:6]])
        for item in sections_raw
        if isinstance(item, dict) and item.get("title")
    ]
    if not sections:
        return None
    return ReadingAssistData(
        paper_id=paper.id,
        mode=mode,
        headline=str(content.get("headline") or ""),
        sections=sections,
        takeaways=[str(x) for x in (content.get("takeaways") or [])[:5]],
        next_steps=[str(x) for x in (content.get("next_steps") or [])[:4]],
        source=str(content.get("source") or "cached"),
        generated=bool(content.get("generated")),
    )


def _persist_reading_assist(session: Session, paper: Paper, data: ReadingAssistData) -> None:
    content_json = {
        "mode": data.mode,
        "headline": data.headline,
        "sections": [section.model_dump() for section in data.sections],
        "takeaways": data.takeaways,
        "next_steps": data.next_steps,
        "source": data.source,
        "generated": data.generated,
    }
    existing = session.scalar(
        select(StructuredResult)
        .where(
            StructuredResult.paper_id == paper.id,
            StructuredResult.result_type == "reading_assist",
        )
        .order_by(StructuredResult.version.desc())
    )
    # Keep one row per mode by bumping version on same type; filter by mode on read.
    version = 1
    same_mode = [
        item
        for item in paper.structured_results
        if item.result_type == "reading_assist" and isinstance(item.content_json, dict) and item.content_json.get("mode") == data.mode
    ]
    if same_mode:
        version = max(item.version for item in same_mode) + 1
    elif existing is not None:
        version = existing.version + 1
    session.add(
        StructuredResult(
            paper_id=paper.id,
            result_type="reading_assist",
            version=version,
            content_json=content_json,
            source_locator={"mode": data.mode, "kind": "reading_assist"},
        )
    )
    session.commit()


def get_related_paper_payloads(session: Session, paper: Paper, *, limit: int = 24) -> list[dict]:
    """Return candidate papers for explainable graph relation ranking."""
    candidates, _ = list_papers(
        session,
        keyword=None,
        keywords=None,
        author=None,
        category=paper.primary_category,
        published_from=None,
        published_to=None,
        page=1,
        page_size=min(max(limit * 3, 30), 100),
    )
    if len(candidates) < limit * 2:
        broader, _ = list_papers(
            session,
            keyword=None,
            keywords=None,
            author=None,
            category=None,
            published_from=None,
            published_to=None,
            page=1,
            page_size=min(max(limit * 4, 50), 100),
        )
        candidates = list({item.id: item for item in [*candidates, *broader]}.values())

    payloads = []
    for item in candidates:
        if item.id == paper.id:
            continue
        payloads.append({
            "paper_id": item.id,
            "arxiv_id": item.arxiv_id or "",
            "title": item.title or "",
            "abstract": item.abstract or "",
            "primary_category": item.primary_category or "",
            "published_at": item.published_at.isoformat() if item.published_at else "",
            "authors": [link.author.display_name for link in sorted(item.authors, key=lambda link: link.author_order)],
        })
    return payloads


def _stored_paper_graph(paper: Paper) -> PaperGraphData | None:
    graph_result = max(
        (item for item in paper.structured_results if item.result_type == "kg_graph"),
        key=lambda item: item.version,
        default=None,
    )
    lineage_result = max(
        (item for item in paper.structured_results if item.result_type == "topic_lineage"),
        key=lambda item: item.version,
        default=None,
    )
    if graph_result is None or not isinstance(graph_result.content_json, dict):
        return None
    graph_content = graph_result.content_json
    lineage_content = lineage_result.content_json if lineage_result and isinstance(lineage_result.content_json, dict) else {}
    if not isinstance(graph_content.get("nodes"), list) or not isinstance(graph_content.get("edges"), list):
        return None
    return PaperGraphData(
        paper_id=paper.id,
        nodes=[GraphNode(**node) for node in graph_content["nodes"] if isinstance(node, dict)],
        edges=[GraphEdge(**edge) for edge in graph_content["edges"] if isinstance(edge, dict)],
        lineage=[LineageItem(**item) for item in lineage_content.get("items", []) if isinstance(item, dict)],
        narrative=str(lineage_content.get("narrative") or ""),
        source=str(graph_content.get("source") or lineage_content.get("source") or "heuristic"),
        generated=True,
        parse_status=parse_status(paper),
        preview=parse_status(paper) not in {"completed", "qa_ready"},
    )


def _persist_paper_graph(session: Session, paper: Paper, graph: PaperGraphData) -> None:
    task_id = next(
        (task.id for task in sorted(paper.parse_tasks, key=lambda item: item.id, reverse=True) if task.status == "succeeded"),
        None,
    )
    rows = {
        "kg_graph": {"nodes": [node.model_dump() for node in graph.nodes], "edges": [edge.model_dump() for edge in graph.edges], "source": graph.source},
        "topic_lineage": {"items": [item.model_dump() for item in graph.lineage], "narrative": graph.narrative, "source": graph.source},
    }
    for result_type, content_json in rows.items():
        result = session.scalar(
            select(StructuredResult)
            .where(StructuredResult.paper_id == paper.id, StructuredResult.result_type == result_type)
            .order_by(StructuredResult.version.desc())
        )
        if result is None:
            result = StructuredResult(
                paper_id=paper.id,
                parse_task_id=task_id,
                result_type=result_type,
                version=1,
                content_json=content_json,
                source_locator={"source": graph.source},
                confidence=0.55,
            )
            session.add(result)
        else:
            result.parse_task_id = task_id
            result.content_json = content_json
            result.source_locator = {"source": graph.source}
    session.commit()


def get_paper_graph(session: Session, paper_id: int, *, settings=None, force: bool = False) -> PaperGraphData:
    paper = get_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)
    if not force:
        stored = _stored_paper_graph(paper)
        if stored is not None:
            return stored
    wiki = get_wiki(session, paper_id)
    graph = GraphAgent(settings or get_settings()).run(
        paper_id=paper.id,
        title=paper.title or "",
        abstract=paper.abstract or wiki.summary or "",
        arxiv_id=paper.arxiv_id or str(paper.id),
        primary_category=paper.primary_category or "",
        published_at=paper.published_at.isoformat() if paper.published_at else "",
        concepts=wiki.concepts,
        methods=wiki.methods,
        experiments=wiki.experiments,
        limitations=wiki.limitations,
        related_papers=get_related_paper_payloads(session, paper),
    )
    data = PaperGraphData(
        paper_id=paper.id,
        nodes=[GraphNode(**node) for node in graph.nodes],
        edges=[GraphEdge(**edge) for edge in graph.edges],
        lineage=[LineageItem(**item) for item in graph.lineage],
        narrative=graph.narrative,
        source=graph.source,
        generated=True,
        parse_status=parse_status(paper),
        preview=parse_status(paper) not in {"completed", "qa_ready"},
    )
    if force:
        _persist_paper_graph(session, paper, data)
    return data


def answer_question(
    session: Session,
    paper_id: int,
    question: str,
    history: list[dict] | None = None,
    *,
    conversation_id: str | None = None,
    settings=None,
) -> QaResponse:
    from app.service.qa_citations import build_retrieval_query, polish_quote, section_label, select_relevant_chunk_ids

    settings = settings or get_settings()
    paper = get_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)
    top_k = min(12, max(5, int(getattr(settings, "qa_agent_top_k", 8))))
    retrieval_query = build_retrieval_query(question, history)
    agent = QaAgent(settings) if settings.qa_agent_ready else None
    search_queries = [retrieval_query]
    rewrite_query = getattr(agent, "rewrite_query", None) if agent is not None else None
    if callable(rewrite_query):
        try:
            plan = rewrite_query(
                title=paper.title or "",
                abstract=paper.abstract or "",
                question=question,
                history=history,
            )
        except LlmError:
            plan = None
        if plan is not None:
            if not plan.paper_related:
                raise PaperServiceError("NO_EVIDENCE", "这个问题与当前论文无关，无法基于论文内容回答", 422)
            search_queries.extend(plan.search_queries)

    matched_by_id = {}
    for query in dict.fromkeys(item.strip() for item in search_queries if item and item.strip()):
        for chunk, score in search_chunks(session, ChunkSearchRequest(query=query, paper_id=paper_id, top_k=top_k)):
            if score < MIN_QA_RETRIEVAL_SCORE:
                continue
            existing = matched_by_id.get(chunk.chunk_id)
            if existing is None or score > existing[1]:
                matched_by_id[chunk.chunk_id] = (chunk, score)
    matches = sorted(
        matched_by_id.values(),
        key=lambda item: (item[1], len(item[0].content or ""), item[0].id),
        reverse=True,
    )[:top_k]
    if not matches:
        raise PaperServiceError("NO_EVIDENCE", "当前论文没有可核验的原文依据，请先完成文本块解析后再提问", 422)

    evidence = [
        {
            "chunk_id": chunk.chunk_id,
            "page_no": chunk.page_no,
            "section": chunk.section,
            "content": chunk.content,
            "score": score,
        }
        for chunk, score in matches
    ]
    chunk_by_id = {chunk.chunk_id: chunk for chunk, _score in matches}
    history_payload = [
        {"role": str(item.get("role") or ""), "content": str(item.get("content") or "")}
        for item in (history or [])
        if isinstance(item, dict) and item.get("role") and item.get("content")
    ]

    if agent is None:
        raise PaperServiceError("QA_AGENT_UNAVAILABLE", "问答 Agent 未配置或未启用，请检查模型配置", 503)
    try:
        generated = agent.run(
            title=paper.title or "",
            question=question,
            evidence=evidence,
            history=history_payload,
        )
    except LlmError as exc:
        raise PaperServiceError("QA_AGENT_FAILED", f"问答生成失败：{exc}", 502) from exc
    if generated.refuse:
        raise PaperServiceError("NO_EVIDENCE", generated.answer or "依据不足，无法核验该问题", 422)
    if not generated.citation_ids:
        raise PaperServiceError("NO_EVIDENCE", "问答 Agent 没有返回有效引用，无法核验回答", 422)
    answer = generated.answer
    selected_ids = select_relevant_chunk_ids(
        answer=answer,
        evidence=evidence,
        preferred_ids=generated.citation_ids,
        min_overlap=0.06,
        max_citations=3,
    )
    answer_mode = "agent"

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
    if not citations:
        raise PaperServiceError("NO_EVIDENCE", "回答没有找到足够的原文依据，请换个问题或先补充解析内容", 422)

    return QaResponse(
        conversation_id=conversation_id or f"conversation-{paper.id}",
        message_id=f"assistant-{uuid4()}",
        paper_id=paper.id,
        answer=answer,
        created_at=datetime.now(timezone.utc),
        citations=citations,
        answer_mode=answer_mode,
    )
