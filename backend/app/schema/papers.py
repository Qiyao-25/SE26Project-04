from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AuthorInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    orcid: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def resolve_name(self):
        value = self.name or self.display_name
        if value is None or not value.strip():
            raise ValueError("作者名称不能为空")
        self.name = " ".join(value.split())
        return self


class PaperUpsert(BaseModel):
    arxiv_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1)
    authors: list[AuthorInput] = Field(default_factory=list)
    abstract: str | None = None
    published_at: datetime | None = None
    primary_category: str | None = Field(default=None, max_length=128)
    pdf_url: str | None = None
    source_url: str | None = None
    ingest_status: str = Field(default="metadata_only", max_length=32)


class PaperItem(BaseModel):
    paper_id: int
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str | None
    published_at: datetime | None
    primary_category: str | None
    pdf_url: str | None
    source_url: str | None
    ingest_status: str
    parse_status: str
    chunk_count: int = 0
    qa_ready: bool = False


class PaperPage(BaseModel):
    items: list[PaperItem]
    total: int
    page: int
    page_size: int
    pages: int


class BatchUpsertResponse(BaseModel):
    items: list[PaperItem]
    created: int
    updated: int


class BatchPaperRequest(BaseModel):
    papers: list[PaperUpsert] = Field(min_length=1, max_length=1000)


class ParseRequest(BaseModel):
    task_type: str = Field(default="full_parse", min_length=1, max_length=64)
    force: bool = False


class TaskResponse(BaseModel):
    task_id: int
    paper_id: int
    task_type: str
    status: Literal["queued", "running", "succeeded", "failed", "timed_out"]
    attempt: int
    idempotency_key: str
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    stage: str | None = None


class TaskUpdate(BaseModel):
    status: Literal["running", "failed", "timed_out"]
    error_code: str | None = Field(default=None, max_length=64)
    stage: str | None = Field(default=None, max_length=32)


class ParsePendingRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class StructuredResultInput(BaseModel):
    result_type: str = Field(min_length=1, max_length=64)
    version: int = Field(default=1, ge=1)
    content_json: dict
    source_locator: dict = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0, le=1)


class StructuredResultBatch(BaseModel):
    results: list[StructuredResultInput] = Field(min_length=1, max_length=20)


class TextChunkInput(BaseModel):
    chunk_id: str = Field(min_length=1, max_length=128)
    page_no: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1)


class TextChunkBatch(BaseModel):
    chunks: list[TextChunkInput] = Field(min_length=1, max_length=5000)


class ChunkSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    paper_id: int | None = Field(default=None, ge=1)
    arxiv_id: str | None = Field(default=None, max_length=128)
    paper_ids: list[int] = Field(default_factory=list, max_length=100)
    top_k: int = Field(default=5, ge=1, le=50)


class ChunkItem(BaseModel):
    paper_id: int
    chunk_id: str
    page_no: int | None
    section: str | None
    content: str
    score: float


class ChunkSearchResponse(BaseModel):
    chunks: list[ChunkItem]


ACTION_TYPES = ("favorite", "reading_history", "reading_progress", "note")


class UserActionInput(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    paper_id: int = Field(ge=1)
    action_type: str = Field(min_length=1, max_length=64)
    payload_json: dict = Field(default_factory=dict)


class UserActionUpdate(BaseModel):
    payload_json: dict = Field(default_factory=dict)


class UserActionItem(BaseModel):
    id: int
    user_id: str
    paper_id: int
    action_type: str
    payload_json: dict
    occurred_at: datetime


class WikiData(BaseModel):
    paper_id: int
    parse_status: str
    summary: str | None
    concepts: list[dict]
    methods: list[dict]
    experiments: list[dict]
    limitations: list[str]
    validation_flags: list[str]
    source_locator: dict
    chunk_count: int = 0
    qa_ready: bool = False


class QaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)


class QaResponse(BaseModel):
    conversation_id: str
    message_id: str
    paper_id: int
    answer: str
    created_at: datetime
    citations: list[dict]
