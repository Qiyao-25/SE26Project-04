from datetime import datetime, timezone
from math import ceil
from uuid import uuid4
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.agents.llm_client import LlmError
from app.agents.qa_agent import QaAgent
from app.agents.graph_agent import GraphAgent
from app.model import Paper, StructuredResult
from app.repository.chunks import search_chunks
from app.repository.papers import (
    compact_search_keywords,
    filter_relevant_papers,
    find_title_candidates,
    get_paper,
    get_papers_by_ids,
    list_papers,
    looks_like_title_query,
    soft_delete_paper,
    title_similarity,
    upsert_paper,
)
from app.schema.papers import (
    AuthorInput,
    BatchUpsertResponse,
    ChunkSearchRequest,
    FetchOnePaperResponse,
    GraphEdge,
    GraphNode,
    LineageItem,
    PaperGraphData,
    PaperItem,
    PaperPage,
    PaperUpsert,
    QaResponse,
    ReadingAssistData,
    ReadingAssistSection,
    SmartSearchResponse,
    WikiData,
)
from app.service.search_query_normalize import paper_matches_excludes
from app.service.search_session_store import create_search_session, get_search_session

logger = logging.getLogger("papermate.papers")

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


def topic_from_category(primary_category: str | None) -> str | None:
    if not primary_category:
        return None
    value = primary_category.strip()
    if "." in value:
        return value.split(".", 1)[0]
    return value


def to_item(paper: Paper) -> PaperItem:
    authors = [link.author.display_name for link in sorted(paper.authors, key=lambda link: link.author_order)]
    return PaperItem(
        paper_id=paper.id,
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=authors,
        abstract=paper.abstract,
        published_at=paper.published_at,
        created_at=getattr(paper, "created_at", None),
        primary_category=paper.primary_category,
        topic=topic_from_category(paper.primary_category),
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
    sort_by = filters.get("sort_by") or "published_desc"
    papers, total = list_papers(session, **filters)
    return PaperPage(
        items=[to_item(paper) for paper in papers],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
        sort_by=sort_by,
    )


def delete_paper(session: Session, paper_id: int) -> PaperItem:
    paper = soft_delete_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", f"论文不存在：{paper_id}", 404)
    return to_item(paper)


def _year_bounds(year_from: int | None, year_to: int | None) -> tuple[datetime | None, datetime | None]:
    published_from = datetime(year_from, 1, 1, tzinfo=timezone.utc) if year_from else None
    published_to = datetime(year_to, 12, 31, 23, 59, 59, tzinfo=timezone.utc) if year_to else None
    return published_from, published_to


def smart_search_papers(
    session: Session,
    *,
    query: str,
    page: int = 1,
    page_size: int = 12,
    category: str | None = None,
    rewritten_query: str | None = None,
    keywords: list[str] | None = None,
    category_hints: list[str] | None = None,
    author_hints: list[str] | None = None,
    search_mode: str | None = None,
    search_session_id: str | None = None,
    include_answer: bool = True,
    settings=None,
) -> SmartSearchResponse:
    from app.agents.search_agent import SearchAgent, SearchPlan
    from app.core.config import get_settings

    settings = settings or get_settings()
    agent = SearchAgent(settings)
    title_mode = looks_like_title_query(query)

    # Prefer server session for pagination (do not re-plan / do not trust client keywords).
    cached = get_search_session(search_session_id)
    if cached and page > 1:
        plan = SearchPlan.from_dict(cached.plan)
        category_filter = category if category is not None else cached.category
        total = len(cached.paper_ids)
        start = (page - 1) * page_size
        page_ids = cached.paper_ids[start:start + page_size]
        papers = get_papers_by_ids(session, page_ids)
        items = [to_item(paper) for paper in papers]
        return SmartSearchResponse(
            query=cached.query or query,
            rewritten_query=plan.rewritten_query or query,
            keywords=plan.keywords,
            intent=plan.intent,
            category=category_filter,
            category_hints=list(plan.category_hints or []),
            author_hints=list(plan.author_hints or []),
            search_mode=plan.search_mode or "topic",
            warnings=list(plan.warnings or []),
            search_session_id=cached.session_id,
            answer="",
            highlights=[],
            plan_source=plan.source or "reused",
            answer_source="skipped",
            citations=[],
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total else 0,
        )

    if rewritten_query or keywords or author_hints:
        # Legacy client reuse — still accepted, but prefer search_session_id.
        plan = SearchPlan(
            rewritten_query=(rewritten_query or query).strip() or query,
            keywords=[item for item in (keywords or []) if item] or [query],
            author_hints=[item for item in (author_hints or []) if item],
            category_hints=[item for item in (category_hints or []) if item],
            search_mode=(search_mode or ("author" if author_hints else "topic")),
            intent="",
            source="reused",
        )
        category_filter = category
    else:
        plan = agent.plan(query)
        category_filter = category if title_mode else (category or (plan.category_hints[0] if plan.category_hints else None))

    published_from, published_to = _year_bounds(plan.year_from, plan.year_to)
    title_hits = find_title_candidates(session, query, limit=max(page_size * 2, 24))
    strong_titles = [p for p in title_hits if title_similarity(query, p.title or "") >= 0.78]
    # Full-title paste: accept slightly lower similarity once candidates were title-scoped.
    if title_mode and not strong_titles and title_hits:
        strong_titles = [p for p in title_hits if title_similarity(query, p.title or "") >= 0.70]

    if title_mode and strong_titles:
        ranked = list(strong_titles)
        category_filter = category
    else:
        mode = plan.search_mode or "topic"
        author_filter = (plan.author_hints or [None])[0]
        if mode == "author" and author_filter:
            search_field = "author"
            raw_keywords = list(plan.author_hints or [author_filter])
        elif mode == "arxiv":
            search_field = "metadata"
            raw_keywords = list(plan.arxiv_ids or plan.keywords or [plan.rewritten_query or query])
        elif title_mode:
            search_field = "title"
            raw_keywords = [query, *(plan.keywords or [])]
        else:
            search_field = "metadata"
            raw_keywords = list(plan.keywords or [])
            if mode == "mixed" and plan.author_hints:
                raw_keywords = [k for k in raw_keywords if k not in plan.author_hints] or list(plan.keywords or [])
            # Prefer canonical aliases as soft keywords without OR explosion
            if plan.aliases:
                raw_keywords = list(dict.fromkeys([*raw_keywords, *plan.aliases[:3]]))

        keywords = compact_search_keywords(raw_keywords, query=None if mode in {"author", "arxiv"} else (plan.rewritten_query or query))
        if not keywords:
            keywords = compact_search_keywords(plan.author_hints or [query])

        def _fetch(kw: list[str], cat: str | None, field: str, *, author: str | None = None) -> list:
            fetch_size = min(max(page_size * 20, 80), 200)
            rows, _ = list_papers(
                session,
                keyword=query if field != "author" else None,
                keywords=None if field == "author" else kw,
                author=author,
                category=cat,
                published_from=published_from,
                published_to=published_to,
                page=1,
                page_size=fetch_size,
                topic=None,
                sort_by="relevance" if field != "author" else "published_desc",
                search_field=field,
            )
            if field == "author":
                return list(rows)
            return filter_relevant_papers(rows, kw or [query], query=query)

        ranked: list = []
        if mode == "author" and plan.author_hints:
            for hint in plan.author_hints[:4]:
                ranked = _fetch([hint], None, "author", author=hint)
                if ranked:
                    break
            if not ranked:
                ranked = _fetch(plan.author_hints[:3], None, "metadata")
        elif mode == "mixed" and plan.author_hints:
            for hint in plan.author_hints[:3]:
                topic_kw = [k for k in keywords if k.casefold() not in {h.casefold() for h in plan.author_hints}] or keywords
                fetch_size = min(max(page_size * 20, 80), 200)
                rows, _ = list_papers(
                    session,
                    keyword=plan.rewritten_query or query,
                    keywords=topic_kw[:3] or None,
                    author=hint,
                    category=category_filter,
                    published_from=published_from,
                    published_to=published_to,
                    page=1,
                    page_size=fetch_size,
                    topic=None,
                    sort_by="relevance",
                    search_field="metadata",
                )
                ranked = filter_relevant_papers(rows, topic_kw or plan.author_hints, query=query)
                if ranked:
                    break
            if not ranked:
                ranked = _fetch(plan.author_hints[:2], None, "author", author=plan.author_hints[0])
                category_filter = None
        else:
            ranked = _fetch(keywords, category_filter, search_field, author=None)
            if not ranked and category_filter and not category:
                ranked = _fetch(keywords, None, search_field)
                category_filter = None
            if not ranked:
                short_kw = keywords[:2] if len(keywords) > 1 else keywords or [query]
                ranked = _fetch(short_kw, None, search_field)
                category_filter = None
            if not ranked and not title_mode:
                ranked = _fetch(compact_search_keywords([query]) or [query], None, "metadata")
                category_filter = None

        if strong_titles:
            strong_ids = {p.id for p in strong_titles}
            rest = [p for p in ranked if p.id not in strong_ids]
            ranked = list(strong_titles) + rest

    if plan.exclude_terms:
        ranked = [paper for paper in ranked if not paper_matches_excludes(paper, plan.exclude_terms)]

    # Cap session snapshot for pagination stability
    ranked = ranked[:500]
    total = len(ranked)
    start = (page - 1) * page_size
    papers = ranked[start:start + page_size]
    items = [to_item(paper) for paper in papers]

    search_session = create_search_session(
        query=query,
        plan=plan.to_dict(),
        paper_ids=[int(paper.id) for paper in ranked if paper.id is not None],
        category=category_filter,
    )

    if include_answer:
        paper_payload = [
            {
                "paper_id": item.paper_id,
                "title": item.title,
                "authors": item.authors,
                "primary_category": item.primary_category,
                "abstract": item.abstract,
                "arxiv_id": item.arxiv_id,
            }
            for item in items[:8]
        ]
        answer = agent.answer(query=query, plan=plan, papers=paper_payload, total=total)
        answer_text = answer.answer
        highlights = answer.highlights
        answer_source = answer.source
        citations = [
            {"paperId": str(pid)}
            for pid in answer.cited_paper_ids
            if any(str(item.paper_id) == str(pid) for item in items)
        ]
    else:
        answer_text = ""
        highlights = []
        answer_source = "skipped"
        citations = []

    return SmartSearchResponse(
        query=query,
        rewritten_query=plan.rewritten_query or query,
        keywords=plan.keywords,
        intent=plan.intent,
        category=category_filter,
        category_hints=list(plan.category_hints or []),
        author_hints=list(plan.author_hints or []),
        search_mode=plan.search_mode or "topic",
        warnings=list(plan.warnings or []),
        search_session_id=search_session.session_id,
        answer=answer_text,
        highlights=highlights,
        plan_source=plan.source,
        answer_source=answer_source,
        citations=citations,
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


def _author_inputs_from_names(raw_authors: list[str] | None) -> list[AuthorInput]:
    authors: list[AuthorInput] = []
    for raw in raw_authors or []:
        name = " ".join(str(raw or "").split()).strip()
        if not name:
            continue
        if len(name) > 255:
            name = name[:255].rstrip()
        try:
            authors.append(AuthorInput(name=name))
        except Exception:  # noqa: BLE001
            continue
        if len(authors) >= 20:
            break
    return authors


def _parse_arxiv_published(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_one_paper(
    session: Session,
    *,
    query: str,
    parse: bool = True,
    settings=None,
) -> FetchOnePaperResponse:
    """Fetch a single paper from arXiv by id/URL/title and upsert into the library."""
    from app.service.arxiv_client import ArxivClient

    text = " ".join((query or "").split()).strip()
    if not text:
        raise PaperServiceError("VALIDATION_ERROR", "请输入 arXiv 编号或论文标题", 400)

    cfg = settings or get_settings()
    client = ArxivClient(
        api_base=getattr(cfg, "arxiv_api_base", "https://export.arxiv.org/api/query"),
        rss_base=getattr(cfg, "arxiv_rss_base", "https://rss.arxiv.org/rss"),
        timeout_s=float(getattr(cfg, "arxiv_timeout_s", 60.0)),
        min_interval_s=float(getattr(cfg, "arxiv_min_interval_s", 5.0)),
        max_retries=int(getattr(cfg, "arxiv_max_retries", 4)),
        rate_limit_wait_s=float(getattr(cfg, "arxiv_rate_limit_wait_s", 45.0)),
    )

    try:
        hits = client.resolve_query(text, max_results=5)
    except Exception as exc:  # noqa: BLE001
        raise PaperServiceError("ARXIV_FETCH_FAILED", f"arXiv 抓取失败：{exc}", 502) from exc

    if not hits:
        raise PaperServiceError("PAPER_NOT_FOUND", "未在 arXiv 找到匹配论文，请检查编号或标题", 404)

    import re

    id_like = bool(
        re.search(r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", text, flags=re.I)
        or re.fullmatch(r"[\w\-]+/\d{7}", text)
    )
    matched_by = "arxiv_id" if id_like else "title"
    meta = hits[0]
    if matched_by == "title" and len(hits) > 1:
        meta = max(hits, key=lambda item: title_similarity(text, item.title or ""))
        if title_similarity(text, meta.title or "") < 0.55:
            raise PaperServiceError("PAPER_NOT_FOUND", "标题匹配度过低，请改用更完整的标题或 arXiv 编号", 404)

    payload = PaperUpsert(
        arxiv_id=meta.arxiv_id,
        title=meta.title or meta.arxiv_id,
        authors=_author_inputs_from_names(meta.authors),
        abstract=meta.abstract,
        published_at=_parse_arxiv_published(meta.published),
        primary_category=(meta.categories[0] if meta.categories else None),
        pdf_url=meta.pdf_url,
        source_url=meta.abs_url,
        ingest_status="metadata_only",
    )
    result = batch_upsert_papers(session, [payload])
    item = result.items[0]
    created = result.created > 0
    message = (
        f"已{'新建' if created else '更新'}论文：{item.title}"
        if matched_by == "arxiv_id"
        else f"已按标题{'入库' if created else '更新'}：{item.title}"
    )

    task = None
    task_id: int | None = None
    if parse:
        from app.service.tasks import create_task

        try:
            task, _ = create_task(
                session,
                item.paper_id,
                "full_parse",
                f"fetch-one-{item.paper_id}-{item.arxiv_id}",
                force=False,
            )
            task_id = task.task_id
            if task.status == "queued":
                message += "；已排队解析"
        except ValueError:
            task = None
            task_id = None

    return FetchOnePaperResponse(
        query=text,
        matched_by=matched_by,
        created=created,
        message=message,
        item=item,
        task_id=task_id,
        task=task,
    )


def get_paper_detail(session: Session, paper_id: int) -> PaperItem:
    paper = get_paper(session, paper_id)
    if paper is None:
        raise PaperServiceError("PAPER_NOT_FOUND", "论文不存在", 404)
    return to_item(paper)


def compare_papers(session: Session, *, paper_id: int, other_paper_id: int, settings=None):
    from app.agents.compare_agent import CompareAgent
    from app.core.config import get_settings
    from app.schema.papers import PaperCompareDimension, PaperCompareResponse

    if paper_id == other_paper_id:
        raise PaperServiceError("COMPARE_SAME_PAPER", "不能与当前论文自身对比", 400)

    left = get_paper(session, paper_id)
    right = get_paper(session, other_paper_id)
    if left is None:
        raise PaperServiceError("PAPER_NOT_FOUND", f"论文不存在：{paper_id}", 404)
    if right is None:
        raise PaperServiceError("PAPER_NOT_FOUND", f"对比论文不存在：{other_paper_id}", 404)

    settings = settings or get_settings()

    def _payload(paper) -> dict:
        item = to_item(paper)
        structured_summary = ""
        try:
            wiki = get_wiki(session, paper.id)
            structured_summary = wiki.summary or ""
        except PaperServiceError:
            structured_summary = ""
        return {
            "title": item.title,
            "authors": item.authors,
            "primary_category": item.primary_category,
            "arxiv_id": item.arxiv_id,
            "abstract": item.abstract or "",
            "summary": structured_summary,
        }

    result = CompareAgent(settings).compare(paper_a=_payload(left), paper_b=_payload(right))
    return PaperCompareResponse(
        paper_id=paper_id,
        other_paper_id=other_paper_id,
        summary=result.summary,
        similarities=result.similarities,
        differences=result.differences,
        dimensions=[
            PaperCompareDimension(
                aspect=item.aspect,
                paper_a=item.paper_a,
                paper_b=item.paper_b,
                comment=item.comment,
            )
            for item in result.dimensions
        ],
        recommendation=result.recommendation,
        source=result.source,
    )


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
