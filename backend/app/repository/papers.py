from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.model import Author, Paper, PaperAuthor
from app.schema.papers import PaperUpsert


def normalize_author_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def upsert_paper(session: Session, payload: PaperUpsert) -> tuple[Paper, bool]:
    paper = session.scalar(select(Paper).where(Paper.arxiv_id == payload.arxiv_id))
    created = paper is None
    if paper is None:
        paper = Paper(arxiv_id=payload.arxiv_id, title=payload.title)
        session.add(paper)

    paper.title = payload.title
    paper.abstract = payload.abstract
    paper.published_at = payload.published_at
    paper.primary_category = payload.primary_category
    paper.pdf_url = payload.pdf_url
    paper.source_url = payload.source_url
    paper.ingest_status = payload.ingest_status

    if payload.authors:
        paper.authors.clear()
        for author_order, author_input in enumerate(payload.authors, start=1):
            normalized_name = normalize_author_name(author_input.name)
            author = session.scalar(select(Author).where(Author.normalized_name == normalized_name))
            if author is None:
                author = Author(normalized_name=normalized_name, display_name=author_input.name, orcid=author_input.orcid)
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
) -> tuple[list[Paper], int]:
    filters = [Paper.deleted_at.is_(None)]
    if keyword:
        pattern = f"%{keyword.strip()}%"
        filters.append(or_(Paper.title.ilike(pattern), Paper.abstract.ilike(pattern), Paper.arxiv_id.ilike(pattern)))
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
    stmt = (
        select(Paper)
        .options(joinedload(Paper.authors).joinedload(PaperAuthor.author))
        .where(*filters)
        .order_by(Paper.published_at.desc().nullslast(), Paper.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(session.scalars(stmt).unique()), total


def get_paper(session: Session, paper_id: int) -> Paper | None:
    stmt = (
        select(Paper)
        .options(joinedload(Paper.authors).joinedload(PaperAuthor.author), joinedload(Paper.content))
        .where(Paper.id == paper_id, Paper.deleted_at.is_(None))
    )
    return session.scalars(stmt).unique().first()
