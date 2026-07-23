from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.model import Paper, TextChunk
from app.schema.papers import ChunkSearchRequest, TextChunkBatch
from app.service.qa_citations import score_chunk


def upsert_chunks(session: Session, paper_id: int, payload: TextChunkBatch) -> int:
    count = _write_chunks(session, paper_id, payload)
    session.commit()
    return count


def replace_chunks(session: Session, paper_id: int, payload: TextChunkBatch) -> int:
    if session.get(Paper, paper_id) is None:
        raise ValueError("PAPER_NOT_FOUND")
    session.query(TextChunk).where(TextChunk.paper_id == paper_id).delete(synchronize_session=False)
    count = _write_chunks(session, paper_id, payload)
    return count


def _write_chunks(session: Session, paper_id: int, payload: TextChunkBatch) -> int:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise ValueError("PAPER_NOT_FOUND")
    for item in payload.chunks:
        chunk = session.scalar(select(TextChunk).where(TextChunk.paper_id == paper_id, TextChunk.chunk_id == item.chunk_id))
        if chunk is None:
            chunk = TextChunk(paper_id=paper_id, chunk_id=item.chunk_id, content=item.content)
            session.add(chunk)
        chunk.page_no = item.page_no
        chunk.section = item.section
        chunk.content = item.content
    session.flush()
    paper.chunk_count = session.scalar(
        select(func.count(TextChunk.id)).where(TextChunk.paper_id == paper_id)
    ) or len(payload.chunks)
    return len(payload.chunks)


def list_chunks_for_paper(session: Session, paper_id: int, *, limit: int = 40) -> list[dict]:
    paper = session.get(Paper, paper_id)
    if paper is None or paper.deleted_at is not None:
        return []
    rows = session.scalars(
        select(TextChunk)
        .where(TextChunk.paper_id == paper_id)
        .order_by(TextChunk.page_no.asc().nullslast(), TextChunk.id.asc())
        .limit(limit)
    ).all()
    return [
        {
            "chunk_id": row.chunk_id,
            "page_no": row.page_no,
            "section": row.section,
            "preview": (row.content or "")[:160],
        }
        for row in rows
        if (row.content or "").strip()
    ]


def search_chunks(session: Session, request: ChunkSearchRequest):
    paper_ids = set(request.paper_ids)
    if request.paper_id:
        paper_ids.add(request.paper_id)
    if request.arxiv_id:
        paper_id = session.scalar(select(Paper.id).where(Paper.arxiv_id == request.arxiv_id, Paper.deleted_at.is_(None)))
        if paper_id:
            paper_ids.add(paper_id)
    stmt = select(TextChunk)
    if paper_ids:
        stmt = stmt.where(TextChunk.paper_id.in_(paper_ids))
    candidates = session.scalars(stmt).all()
    scored = []
    for chunk in candidates:
        score = score_chunk(request.query, chunk.content or "")
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (item[0], len(item[1].content or ""), item[1].id), reverse=True)
    if scored:
        return [(chunk, round(score, 6)) for score, chunk in scored[: request.top_k]]

    weak = sorted(
        candidates,
        key=lambda chunk: (-len(chunk.content or ""), chunk.id),
    )
    weak = [
        chunk for chunk in weak
        if len(chunk.content or "") >= 80
        and "permission to reproduce" not in (chunk.content or "").lower()
        and "arxiv:" not in (chunk.content or "").lower()
    ][: request.top_k]
    return [(chunk, 0.01) for chunk in weak]
