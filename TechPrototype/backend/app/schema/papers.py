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
    created_at: datetime | None = None
    primary_category: str | None
    topic: str | None = None
    pdf_url: str | None
    source_url: str | None
    ingest_status: str
    parse_status: str
    chunk_count: int = 0
    qa_ready: bool = False
    reason: str | None = None
    recommend_source: str | None = None


class PaperPage(BaseModel):
    items: list[PaperItem]
    total: int
    page: int
    page_size: int
    pages: int
    sort_by: str | None = None


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
    retryable: bool = False


class TaskQueueStats(BaseModel):
    counts: dict[str, int]
    retryable_failed: int
    stale_running: int
    oldest_queued_at: datetime | None = None


class TaskClaimRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=128)


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


class ParseResultCommit(BaseModel):
    chunks: list[TextChunkInput] = Field(min_length=1, max_length=5000)
    results: list[StructuredResultInput] = Field(min_length=1, max_length=20)


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


PERSONAS = ("新手", "研究", "工程", "教学", "管理")


class UserProfileUpdate(BaseModel):
    """Partial update: omitted fields keep existing values."""

    persona: str | None = Field(default=None, max_length=32)
    topics: list[str] | None = Field(default=None, max_length=20)
    preferences: dict | None = None


class UserProfileData(BaseModel):
    user_id: str
    persona: str = Field(default="研究", max_length=32)
    topics: list[str] = Field(default_factory=list, max_length=20)
    preferences: dict = Field(default_factory=dict)


class SubscriptionItem(BaseModel):
    key: str
    type: Literal["keyword", "category"]
    value: str
    enabled: bool = True


class SubscriptionSaveRequest(BaseModel):
    subscriptions: list[SubscriptionItem] = Field(default_factory=list, max_length=30)


class SubscriptionSyncResult(BaseModel):
    user_id: str
    fetched: int = 0
    created: int = 0
    updated: int = 0
    deduped: int = 0
    paper_ids: list[int] = Field(default_factory=list)
    message: str = ""
    synced_at: datetime | None = None
    errors: list[str] = Field(default_factory=list)


class DictionaryEntry(BaseModel):
    term: str
    description: str
    paper_ids: list[int] = Field(default_factory=list)
    paper_titles: list[str] = Field(default_factory=list)


class WikiData(BaseModel):
    paper_id: int
    parse_status: str
    summary: str | None
    concepts: list[dict]
    methods: list[dict]
    experiments: list[dict]
    limitations: list[str]
    validation_flags: list[str]
    validation_labels: list[str] = Field(default_factory=list)
    uncertain_fields: list[str] = Field(default_factory=list)
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
    # agent = LLM 问答；extractive_fallback = 原文摘录降级（非 Agent 总结）
    answer_mode: str = "agent"


class SmartSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=50)
    category: str | None = Field(default=None, max_length=128)
    rewritten_query: str | None = Field(default=None, max_length=500)
    keywords: list[str] | None = None
    category_hints: list[str] | None = None
    author_hints: list[str] | None = None
    search_mode: str | None = Field(default=None, max_length=32)
    search_session_id: str | None = Field(default=None, max_length=64)
    include_answer: bool = True


class SmartSearchResponse(BaseModel):
    query: str
    rewritten_query: str
    keywords: list[str]
    intent: str = ""
    category: str | None = None
    category_hints: list[str] = Field(default_factory=list)
    author_hints: list[str] = Field(default_factory=list)
    search_mode: str = "topic"
    warnings: list[str] = Field(default_factory=list)
    search_session_id: str | None = None
    answer: str
    highlights: list[str] = Field(default_factory=list)
    plan_source: str = "heuristic"
    answer_source: str = "template"
    citations: list[dict] = Field(default_factory=list)
    items: list[PaperItem]
    total: int
    page: int
    page_size: int
    pages: int


class FetchOnePaperRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500, description="arXiv 编号、abs/pdf 链接或论文标题")
    parse: bool = Field(default=True, description="入库后是否自动排队解析")


class FetchOnePaperResponse(BaseModel):
    query: str
    matched_by: Literal["arxiv_id", "title"]
    created: bool
    message: str
    item: PaperItem
    task_id: int | None = None
    task: TaskResponse | None = None


class ReadingAssistRequest(BaseModel):
    mode: str = Field(default="研究", max_length=16)
    force: bool = False


class PaperCompareRequest(BaseModel):
    other_paper_id: int = Field(ge=1)


class PaperCompareDimension(BaseModel):
    aspect: str
    paper_a: str = ""
    paper_b: str = ""
    comment: str = ""


class PaperCompareResponse(BaseModel):
    paper_id: int
    other_paper_id: int
    summary: str
    similarities: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    dimensions: list[PaperCompareDimension] = Field(default_factory=list)
    recommendation: str = ""
    source: str = "template"


class ReadingAssistSection(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)


class ReadingAssistData(BaseModel):
    paper_id: int
    mode: str
    headline: str = ""
    sections: list[ReadingAssistSection] = Field(default_factory=list)
    takeaways: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    source: str = "heuristic"
    generated: bool = False


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    paper_id: int | None = None
    arxiv_id: str | None = None
    role: str | None = None
    lane: str | None = None
    published_at: str | None = None
    description: str | None = None
    score: float | None = Field(default=None, ge=0, le=1)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    label: str = ""
    tier: str | None = None
    weight: float | None = Field(default=None, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class LineageItem(BaseModel):
    paper_id: int | None = None
    arxiv_id: str = ""
    title: str = ""
    published_at: str = ""
    role: str = "related"
    note: str = ""


class PaperGraphData(BaseModel):
    paper_id: int
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    lineage: list[LineageItem] = Field(default_factory=list)
    narrative: str = ""
    source: str = "heuristic"
    generated: bool = False
    parse_status: str = "pending"
    preview: bool = True
