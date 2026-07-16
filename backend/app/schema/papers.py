from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AuthorInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    orcid: str | None = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("作者名称不能为空")
        return value


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


class WikiData(BaseModel):
    paper_id: int
    parse_status: str
    summary: str | None
    concepts: list[dict]
    methods: list[dict]
    limitations: list[str]
    source_locator: dict


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
