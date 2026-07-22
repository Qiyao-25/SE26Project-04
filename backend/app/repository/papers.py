from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.model import Author, Paper, PaperAuthor
from app.schema.papers import PaperUpsert


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
) -> tuple[list[Paper], int]:
    filters = [Paper.deleted_at.is_(None)]
    keyword_terms = [item.strip() for item in (keywords or []) if item and item.strip()]
    if not keyword_terms and keyword and keyword.strip():
        keyword_terms = [keyword.strip()]
    if keyword_terms:
        term_filters = []
        for term in keyword_terms[:12]:
            pattern = f"%{term}%"
            term_filters.extend([
                Paper.title.ilike(pattern),
                Paper.abstract.ilike(pattern),
                Paper.arxiv_id.ilike(pattern),
                Paper.primary_category.ilike(pattern),
            ])
        filters.append(or_(*term_filters))
    if author:
        author_pattern = f"%{author.strip()}%"
        filters.append(Paper.authors.any(PaperAuthor.author.has(Author.display_name.ilike(author_pattern))))
    if category:
        filters.append(Paper.primary_category == category)
    if published_from:
        filters.append(Paper.published_at >= published_from)
    if published_to:
        filters.append(Paper.published_at <= published_to)

    count_stmt = select(func.count(Paper.id)).where(*filters)
    total = session.scalar(count_stmt) or 0
    if keyword_terms:
        # Fetch a window large enough for the requested page after relevance re-ranking.
        need = page * page_size
        fetch_size = min(max(need + page_size * 2, page_size * 5), 500)
        stmt = (
            select(Paper)
            .options(joinedload(Paper.authors).joinedload(PaperAuthor.author))
            .where(*filters)
            .order_by(Paper.published_at.desc().nullslast(), Paper.id.desc())
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
        .order_by(Paper.published_at.desc().nullslast(), Paper.id.desc())
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
