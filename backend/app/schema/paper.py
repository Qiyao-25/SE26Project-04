from typing import Literal

from pydantic import BaseModel, Field


class PaperListItem(BaseModel):
    paperId: str
    title: str
    authors: list[str]
    primaryCategory: str
    arxivId: str
    publishedAt: str
    summary: str
    keywords: list[str]
    researchDirection: str = ""
    conceptTags: list[str] = []
    parseStatus: Literal["pending", "parsing", "completed", "failed"] = "completed"
    isFavorite: bool = False


class PaperDetail(PaperListItem):
    categories: list[str]
    doi: str | None = None
    updatedAt: str
    abstract: str
    pdfUrl: str
    sourceUrl: str
    codeUrl: str | None = None


class SearchRequest(BaseModel):
    query: str = ""
    searchType: str = "keyword"
    categories: list[str] = []
    sortBy: str = "relevance"
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=12, ge=1, le=100)


class SearchResult(BaseModel):
    searchId: str
    query: str
    searchType: str
    sortBy: str
    total: int
    page: int
    pageSize: int
    searchTimeMs: int
    items: list[PaperListItem]


class PaperSection(BaseModel):
    sectionId: str
    title: str
    pageStart: int | None = None
    pageEnd: int | None = None


class PaperContent(BaseModel):
    paperId: str
    contentType: str
    pdfUrl: str | None = None
    htmlUrl: str | None = None
    pageCount: int | None = None
    defaultPage: int = 1
    sections: list[PaperSection] = []


class ConceptItem(BaseModel):
    conceptId: str
    name: str
    description: str


class MethodItem(BaseModel):
    order: int
    title: str
    description: str


class ExperimentItem(BaseModel):
    title: str
    description: str


class PaperSummary(BaseModel):
    paperId: str
    parseStatus: Literal["pending", "parsing", "completed", "failed"]
    summary: str
    concepts: list[ConceptItem]
    methods: list[MethodItem]
    experiments: list[ExperimentItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    validationFlags: list[str] = Field(default_factory=list)
