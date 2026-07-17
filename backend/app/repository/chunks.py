import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import Paper, TextChunk
from app.schema.papers import ChunkSearchRequest, TextChunkBatch


_EN_STOPWORDS = {
    "a", "an", "and", "are", "be", "by", "can", "do", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "what", "when", "where", "which", "who", "why", "with",
}


def _tokens(value: str) -> set[str]:
    normalized = value.casefold()
    english = {
        token for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 1 and token not in _EN_STOPWORDS
    }
    chinese = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        chinese.update(run[index:index + 2] for index in range(len(run) - 1))
    return english | chinese


def upsert_chunks(session: Session, paper_id: int, payload: TextChunkBatch) -> int:
    if session.get(Paper, paper_id) is None:
        raise ValueError("PAPER_NOT_FOUND")
    for item in payload.chunks:
        chunk = session.scalar(select(TextChunk).where(TextChunk.paper_id == paper_id, TextChunk.chunk_id == item.chunk_id))
        if chunk is None:
            chunk = TextChunk(paper_id=paper_id, chunk_id=item.chunk_id, content=item.content)
            session.add(chunk)
        chunk.page_no = item.page_no
        chunk.section = item.section
        chunk.content = item.content
    session.commit()
    return len(payload.chunks)


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
    query_tokens = _tokens(request.query)
    scored = []
    for chunk in candidates:
        content_tokens = _tokens(chunk.content)
        overlap = len(query_tokens & content_tokens)
        score = overlap / max(len(query_tokens), 1)
        if request.query.casefold() in chunk.content.casefold():
            score += 0.5
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
    return [(chunk, round(score, 6)) for score, chunk in scored[: request.top_k]]
