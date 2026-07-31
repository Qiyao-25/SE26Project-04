from typing import Literal

from pydantic import BaseModel, Field


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
    sections: list[PaperSection] = Field(default_factory=list)


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
    parseStatus: Literal["pending", "queued", "parsing", "completed", "qa_ready", "failed"]
    summary: str = ""
    concepts: list[ConceptItem] = Field(default_factory=list)
    methods: list[MethodItem] = Field(default_factory=list)
    experiments: list[ExperimentItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    validationFlags: list[str] = Field(default_factory=list)
    validationLabels: list[str] = Field(default_factory=list)
    uncertainFields: list[str] = Field(default_factory=list)
    chunkCount: int = 0
    qaReady: bool = False
