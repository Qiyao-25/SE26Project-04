from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schema.common import ApiResponse
from app.schema.papers import ChunkItem, ChunkSearchRequest, ChunkSearchResponse
from app.repository.chunks import search_chunks

router = APIRouter(tags=["search"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


def _search(request: ChunkSearchRequest, session: Session) -> ChunkSearchResponse:
    return ChunkSearchResponse(
        chunks=[
            ChunkItem(
                paper_id=chunk.paper_id,
                chunk_id=chunk.chunk_id,
                page_no=chunk.page_no,
                section=chunk.section,
                content=chunk.content,
                score=score,
            )
            for chunk, score in search_chunks(session, request)
        ]
    )


@router.post("/api/search/chunks", response_model=ApiResponse[ChunkSearchResponse], summary="检索论文文本块")
def search_chunks_api(request: ChunkSearchRequest, http_request: Request, db: Session = Depends(db_session)):
    return ApiResponse(data=_search(request, db), request_id=http_request.state.request_id)


@router.post("/search/chunks", response_model=ApiResponse[ChunkSearchResponse], include_in_schema=False)
def search_chunks_legacy(request: ChunkSearchRequest, http_request: Request, db: Session = Depends(db_session)):
    return ApiResponse(data=_search(request, db), request_id=http_request.state.request_id)
