from datetime import datetime, timezone

from sqlalchemy import Text, cast, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.model import Author, Paper, PaperAuthor, StructuredResult
from app.schema.papers import PaperUpsert

# arXiv 学科大类（主题）前缀 → 对应 primary_category 匹配规则
TOPIC_PREFIXES = {
    "cs": "cs.",
    "stat": "stat.",
    "math": "math.",
    "eess": "eess.",
    "physics": "physics.",
    "cond-mat": "cond-mat.",
    "quant-ph": "quant-ph",
    "hep-th": "hep-th",
    "astro-ph": "astro-ph.",
    "gr-qc": "gr-qc",
    "nlin": "nlin.",
    "q-bio": "q-bio.",
    "q-fin": "q-fin.",
    "econ": "econ.",
}

SORT_OPTIONS = {
    "published_desc",
    "published_asc",
    "created_desc",
    "created_asc",
    "title_asc",
    "title_desc",
    "id_asc",
    "id_desc",
    "author_asc",
    "author_desc",
    "topic_asc",
    "topic_desc",
    "category_asc",
    "category_desc",
    "arxiv_asc",
    "arxiv_desc",
    "status_asc",
    "status_desc",
    "relevance",
}

SEARCH_FIELDS = {"all", "title", "author", "keyword", "direction", "concept"}


def normalize_author_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def upsert_paper(session: Session, payload: PaperUpsert) -> tuple[Paper, bool]:
    from app.service.dedupe import normalize_arxiv_id

    arxiv_id = normalize_arxiv_id(payload.arxiv_id)
    paper = session.scalar(select(Paper).where(Paper.arxiv_id == arxiv_id))
    created = paper is None

    if paper is None:
        paper = Paper(arxiv_id=arxiv_id, title=payload.title)
        session.add(paper)
        created = True

    paper.arxiv_id = paper.arxiv_id or arxiv_id
    paper.title = payload.title
    paper.abstract = payload.abstract
    paper.published_at = payload.published_at
    paper.primary_category = payload.primary_category
    paper.pdf_url = payload.pdf_url
    paper.source_url = payload.source_url
    # Do not downgrade a richer ingest_status on metadata updates.
    if created or paper.ingest_status in {None, "", "metadata_only"}:
        paper.ingest_status = payload.ingest_status

    if payload.authors:
        paper.authors.clear()
        for author_order, author_input in enumerate(payload.authors, start=1):
            normalized_name = normalize_author_name(author_input.name or author_input.display_name or "")
            author = session.scalar(select(Author).where(Author.normalized_name == normalized_name))
            if author is None:
                author = Author(
                    normalized_name=normalized_name,
                    display_name=author_input.name or author_input.display_name or "",
                    orcid=author_input.orcid,
                )
                session.add(author)
            elif author_input.orcid and not author.orcid:
                author.orcid = author_input.orcid
            paper.authors.append(PaperAuthor(author=author, author_order=author_order))

    return paper, created


def _first_author_name():
    return (
        select(Author.display_name)
        .select_from(PaperAuthor)
        .join(Author, Author.id == PaperAuthor.author_id)
        .where(PaperAuthor.paper_id == Paper.id)
        .order_by(PaperAuthor.author_order.asc())
        .limit(1)
        .scalar_subquery()
        .correlate(Paper)
    )


def _order_clause(sort_by: str):
    first_author = _first_author_name()
    category_key = func.lower(func.coalesce(Paper.primary_category, ""))
    if sort_by == "published_asc":
        return (Paper.published_at.asc().nullslast(), Paper.id.asc())
    if sort_by == "created_desc":
        return (Paper.created_at.desc().nullslast(), Paper.id.desc())
    if sort_by == "created_asc":
        return (Paper.created_at.asc().nullslast(), Paper.id.asc())
    if sort_by == "title_asc":
        return (func.lower(Paper.title).asc(), Paper.id.asc())
    if sort_by == "title_desc":
        return (func.lower(Paper.title).desc(), Paper.id.desc())
    if sort_by == "id_asc":
        return (Paper.id.asc(),)
    if sort_by == "id_desc":
        return (Paper.id.desc(),)
    if sort_by == "author_asc":
        return (func.lower(func.coalesce(first_author, "")).asc(), Paper.id.asc())
    if sort_by == "author_desc":
        return (func.lower(func.coalesce(first_author, "")).desc(), Paper.id.desc())
    if sort_by == "topic_asc":
        return (category_key.asc(), Paper.id.asc())
    if sort_by == "topic_desc":
        return (category_key.desc(), Paper.id.desc())
    if sort_by == "category_asc":
        return (category_key.asc(), Paper.id.asc())
    if sort_by == "category_desc":
        return (category_key.desc(), Paper.id.desc())
    if sort_by == "arxiv_asc":
        return (func.lower(Paper.arxiv_id).asc(), Paper.id.asc())
    if sort_by == "arxiv_desc":
        return (func.lower(Paper.arxiv_id).desc(), Paper.id.desc())
    if sort_by == "status_asc":
        return (func.lower(Paper.ingest_status).asc(), Paper.id.asc())
    if sort_by == "status_desc":
        return (func.lower(Paper.ingest_status).desc(), Paper.id.desc())
    # published_desc / relevance fallback
    return (Paper.published_at.desc().nullslast(), Paper.id.desc())


def _topic_filter(topic: str):
    raw = topic.strip()
    if not raw:
        return None
    key = raw.casefold()
    prefix = TOPIC_PREFIXES.get(key)
    if prefix:
        if prefix.endswith("."):
            return or_(Paper.primary_category == key, Paper.primary_category.ilike(f"{prefix}%"))
        return or_(Paper.primary_category == prefix, Paper.primary_category.ilike(f"{prefix}.%"))
    # free-form: exact category or prefix group
    if "." in raw:
        return Paper.primary_category == raw
    return or_(Paper.primary_category == raw, Paper.primary_category.ilike(f"{raw}.%"))


def _structured_text_exists(pattern: str, result_types: list[str]):
    json_text = cast(StructuredResult.content_json, Text)
    return exists(
        select(1)
        .where(
            StructuredResult.paper_id == Paper.id,
            StructuredResult.result_type.in_(result_types),
            json_text.ilike(pattern),
        )
        .correlate(Paper)
    )


def list_papers(
    session: Session,
    *,
    keyword: str | None,
    author: str | None,
    category: str | None,
    published_from: datetime | None,
    published_to: datetime | None,
    page: int,
    page_size: int,
    keywords: list[str] | None = None,
    topic: str | None = None,
    sort_by: str = "published_desc",
    search_field: str = "all",
) -> tuple[list[Paper], int]:
    filters = [Paper.deleted_at.is_(None)]
    sort_by = sort_by if sort_by in SORT_OPTIONS else "published_desc"
    search_field = search_field if search_field in SEARCH_FIELDS else "all"

    keyword_terms = [item.strip() for item in (keywords or []) if item and item.strip()]
    if not keyword_terms and keyword and keyword.strip():
        keyword_terms = [keyword.strip()]

    # Author can come from dedicated param or from author search_field
    author_query = author.strip() if author and author.strip() else None
    if search_field == "author" and keyword_terms and not author_query:
        author_query = keyword_terms[0]
        keyword_terms = []

    if keyword_terms and search_field != "author":
        term_filters = []
        for term in keyword_terms[:12]:
            pattern = f"%{term}%"
            if search_field == "title":
                term_filters.append(Paper.title.ilike(pattern))
            elif search_field == "direction":
                term_filters.extend([
                    Paper.primary_category.ilike(pattern),
                    Paper.title.ilike(pattern),
                ])
            elif search_field == "concept":
                term_filters.append(_structured_text_exists(pattern, ["concepts", "wiki_triple", "summary"]))
            elif search_field == "keyword":
                term_filters.extend([
                    Paper.title.ilike(pattern),
                    Paper.abstract.ilike(pattern),
                    _structured_text_exists(pattern, ["concepts", "wiki_triple", "summary", "methods"]),
                ])
            else:  # all
                term_filters.extend([
                    Paper.title.ilike(pattern),
                    Paper.abstract.ilike(pattern),
                    Paper.arxiv_id.ilike(pattern),
                    Paper.primary_category.ilike(pattern),
                    _structured_text_exists(pattern, ["concepts", "wiki_triple"]),
                ])
        if term_filters:
            filters.append(or_(*term_filters))

    if author_query:
        author_pattern = f"%{author_query}%"
        filters.append(Paper.authors.any(PaperAuthor.author.has(Author.display_name.ilike(author_pattern))))
    if category:
        filters.append(Paper.primary_category == category.strip())
    topic_clause = _topic_filter(topic) if topic else None
    if topic_clause is not None:
        filters.append(topic_clause)
    if published_from:
        filters.append(Paper.published_at >= published_from)
    if published_to:
        filters.append(Paper.published_at <= published_to)

    count_stmt = select(func.count(Paper.id)).where(*filters)
    total = session.scalar(count_stmt) or 0

    use_relevance = sort_by == "relevance" and bool(keyword_terms)
    order = _order_clause("published_desc" if use_relevance else sort_by)

    if use_relevance:
        # Fetch a window large enough for the requested page after relevance re-ranking.
        need = page * page_size
        fetch_size = min(max(need + page_size * 2, page_size * 5), 500)
        stmt = (
            select(Paper)
            .options(joinedload(Paper.authors).joinedload(PaperAuthor.author))
            .where(*filters)
            .order_by(*order)
            .limit(fetch_size)
        )
        papers = list(session.scalars(stmt).unique())
        papers = _rank_papers(papers, keyword_terms)
        start = (page - 1) * page_size
        if start >= total:
            return [], total
        # Do not pad the last page: return only remaining items (e.g. 8 of 12).
        end = min(start + page_size, total, len(papers))
        return papers[start:end], total

    stmt = (
        select(Paper)
        .options(joinedload(Paper.authors).joinedload(PaperAuthor.author))
        .where(*filters)
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(session.scalars(stmt).unique()), total


def _rank_papers(papers: list[Paper], keywords: list[str]) -> list[Paper]:
    lowered = [keyword.casefold() for keyword in keywords if keyword]

    def score(paper: Paper) -> tuple[int, int]:
        blob = " ".join([paper.title or "", paper.abstract or "", paper.arxiv_id or "", paper.primary_category or ""]).casefold()
        hits = sum(1 for keyword in lowered if keyword in blob)
        title_hits = sum(1 for keyword in lowered if keyword in (paper.title or "").casefold())
        return (title_hits * 3 + hits, len(paper.abstract or ""))

    return sorted(papers, key=score, reverse=True)


def get_paper(session: Session, paper_id: int) -> Paper | None:
    stmt = (
        select(Paper)
        .options(joinedload(Paper.authors).joinedload(PaperAuthor.author), joinedload(Paper.content))
        .where(Paper.id == paper_id, Paper.deleted_at.is_(None))
    )
    return session.scalars(stmt).unique().first()


def soft_delete_paper(session: Session, paper_id: int) -> Paper | None:
    paper = get_paper(session, paper_id)
    if paper is None:
        return None
    paper.deleted_at = datetime.now(timezone.utc)
    session.add(paper)
    session.commit()
    session.refresh(paper)
    return paper
