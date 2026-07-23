import re
from difflib import SequenceMatcher
from datetime import datetime, timezone

from sqlalchemy import Text, and_, cast, exists, func, or_, select
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

SEARCH_FIELDS = {"all", "title", "author", "keyword", "direction", "concept", "metadata"}

# Smart-search / metadata ranking ignores these weak tokens.
SEARCH_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "for", "to", "with", "via", "by",
    "from", "into", "over", "under", "using", "based", "paper", "study", "method",
    "model", "models", "learning", "data", "approach", "towards", "toward", "via",
    "一种", "基于", "通过", "研究", "方法", "模型", "论文", "学习", "数据",
}


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
                # Wiki concept mode only — not used by smart search.
                term_filters.append(_structured_text_exists(pattern, ["concepts", "wiki_triple", "summary"]))
            elif search_field == "keyword":
                term_filters.extend([
                    Paper.title.ilike(pattern),
                    Paper.abstract.ilike(pattern),
                ])
            elif search_field == "metadata":
                # Smart search: AND core terms across topic/title/author/arxiv/abstract only.
                # (Built after the loop — see below.)
                pass
            else:  # all — library keyword box; still metadata-only (no parse/wiki 出处)
                term_filters.extend([
                    Paper.title.ilike(pattern),
                    Paper.abstract.ilike(pattern),
                    Paper.arxiv_id.ilike(pattern),
                    Paper.primary_category.ilike(pattern),
                    Paper.authors.any(PaperAuthor.author.has(Author.display_name.ilike(pattern))),
                ])
        if search_field == "metadata" and keyword_terms:
            per_term: list = []
            for term in keyword_terms[:4]:
                pattern = f"%{term}%"
                per_term.append(
                    or_(
                        Paper.title.ilike(pattern),
                        Paper.abstract.ilike(pattern),
                        Paper.arxiv_id.ilike(pattern),
                        Paper.primary_category.ilike(pattern),
                        Paper.authors.any(PaperAuthor.author.has(Author.display_name.ilike(pattern))),
                    )
                )
            # Require every core term (up to 3) to match somewhere → fewer weak hits.
            core = per_term[:3] if len(per_term) >= 2 else per_term
            filters.append(and_(*core) if len(core) > 1 else core[0])
        elif term_filters:
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
        papers = _rank_papers(papers, keyword_terms, query=keyword or " ".join(keyword_terms))
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


def _normalize_title(value: str | None) -> str:
    text = (value or "").casefold()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def looks_like_title_query(query: str | None) -> bool:
    """Heuristic: long / multi-token queries are treated as title lookups."""
    q = (query or "").strip()
    if not q:
        return False
    if len(q) >= 36:
        return True
    latin_words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}", q)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", q)
    if len(latin_words) >= 5:
        return True
    if len(cjk_chars) >= 12:
        return True
    return False


def title_similarity(query: str, title: str) -> float:
    nq = _normalize_title(query)
    nt = _normalize_title(title)
    if not nq or not nt:
        return 0.0
    if nq == nt:
        return 1.0
    if nq in nt or nt in nq:
        return max(0.93, SequenceMatcher(None, nq, nt).ratio())
    ratio = SequenceMatcher(None, nq, nt).ratio()
    # token overlap for slight title differences
    q_tokens = set(nq.split())
    t_tokens = set(nt.split())
    if q_tokens and t_tokens:
        overlap = len(q_tokens & t_tokens) / max(len(q_tokens), 1)
        if overlap >= 0.7:
            ratio = max(ratio, 0.7 + 0.25 * overlap)
    return ratio


def compact_search_keywords(keywords: list[str] | None, query: str | None = None) -> list[str]:
    """Keep stronger tokens only — reduces weak OR/AND matches in smart search."""
    raw = [item.strip() for item in (keywords or []) if item and str(item).strip()]
    if query and query.strip():
        # Prefer splitting a multi-word query into tokens rather than AND-ing the whole phrase.
        parts = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}|[\u4e00-\u9fff]{2,}", query.strip())
        if len(parts) >= 2:
            for part in parts:
                if part not in raw:
                    raw.append(part)
        elif query.strip() not in raw:
            raw.insert(0, query.strip())
    cleaned: list[str] = []
    seen: set[str] = set()
    for term in raw:
        # Skip long multi-word phrases when we already collect tokens (AND would over-constrain).
        if " " in term and len(term.split()) >= 3:
            continue
        key = term.casefold()
        if key in seen:
            continue
        if key in SEARCH_STOPWORDS:
            continue
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", term))
        if has_cjk and len(re.findall(r"[\u4e00-\u9fff]", term)) < 2:
            continue
        if not has_cjk and len(term) < 3 and not re.match(r"^\d{4}\.\d{4,}$", term):
            continue
        seen.add(key)
        cleaned.append(term)
        if len(cleaned) >= 5:
            break
    return cleaned or ([query.strip()] if query and query.strip() else [])


def paper_metadata_score(paper: Paper, keywords: list[str], query: str | None = None) -> float:
    """Higher is better. Category-only hits score low and can be filtered out."""
    lowered = [k.casefold() for k in keywords if k]
    title = (paper.title or "").casefold()
    abstract = (paper.abstract or "").casefold()
    arxiv = (paper.arxiv_id or "").casefold()
    category = (paper.primary_category or "").casefold()
    authors = " ".join(
        link.author.display_name for link in sorted(paper.authors, key=lambda link: link.author_order)
    ).casefold()

    sim = title_similarity(query, paper.title or "") if query else 0.0
    score = sim * 40.0
    title_hits = 0
    abstract_hits = 0
    author_hits = 0
    code_hits = 0
    topic_hits = 0
    for keyword in lowered:
        if keyword in title:
            title_hits += 1
            score += 8.0
        if keyword in abstract:
            abstract_hits += 1
            score += 3.0
        if keyword in authors:
            author_hits += 1
            score += 6.0
        if keyword in arxiv:
            code_hits += 1
            score += 10.0
        # Topic/category: only count reasonably specific tokens
        if keyword in category and (len(keyword) >= 4 or "." in keyword):
            topic_hits += 1
            score += 2.0

    # Drop category-only / abstract-only weak noise unless title is near-match.
    substantive = title_hits + abstract_hits + author_hits + code_hits
    if sim < 0.72 and substantive == 0:
        return 0.0
    if sim < 0.72 and title_hits + author_hits + code_hits == 0 and abstract_hits < 2:
        # Single abstract token match is usually weak-related.
        return min(score, 2.9)
    _ = topic_hits  # counted in score when specific enough
    return score


def _rank_papers(papers: list[Paper], keywords: list[str], query: str | None = None) -> list[Paper]:
    def score(paper: Paper) -> tuple[float, int]:
        return (paper_metadata_score(paper, keywords, query), -int(paper.id or 0))

    return sorted(papers, key=score, reverse=True)


def filter_relevant_papers(
    papers: list[Paper],
    keywords: list[str],
    query: str | None = None,
    *,
    min_score: float = 5.0,
) -> list[Paper]:
    ranked = _rank_papers(papers, keywords, query=query)
    kept = [paper for paper in ranked if paper_metadata_score(paper, keywords, query) >= min_score]
    if query:
        for paper in ranked:
            if title_similarity(query, paper.title or "") >= 0.78 and paper not in kept:
                kept.append(paper)
    return kept


def find_title_candidates(session: Session, query: str, *, limit: int = 40) -> list[Paper]:
    """Find papers whose titles are near-matches to the query (slight typos / punctuation diffs)."""
    q = (query or "").strip()
    if not q:
        return []
    tokens = [t for t in _normalize_title(q).split() if len(t) >= 3][:8]
    filters = [Paper.deleted_at.is_(None)]
    if tokens:
        term_filters = [Paper.title.ilike(f"%{token}%") for token in tokens]
        # Also try a long contiguous fragment of the raw query.
        frag = q.strip()[:80]
        if len(frag) >= 12:
            term_filters.append(Paper.title.ilike(f"%{frag}%"))
        filters.append(or_(*term_filters))
    else:
        filters.append(Paper.title.ilike(f"%{q[:80]}%"))
    stmt = (
        select(Paper)
        .options(joinedload(Paper.authors).joinedload(PaperAuthor.author))
        .where(*filters)
        .limit(min(max(limit * 3, 60), 300))
    )
    papers = list(session.scalars(stmt).unique())
    ranked = sorted(papers, key=lambda p: (title_similarity(q, p.title or ""), -p.id), reverse=True)
    strong = [p for p in ranked if title_similarity(q, p.title or "") >= 0.72]
    return (strong or ranked)[:limit]


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
