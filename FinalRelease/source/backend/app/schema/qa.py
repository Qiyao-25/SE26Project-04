from typing import Literal

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: str
    content: str


QaScope = Literal["both", "wiki", "chunks"]


class AskPaperRequest(BaseModel):
    conversationId: str | None = None
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessage] = []
    # both = Wiki 结构化知识 + 原文块；wiki = 仅 Wiki；chunks = 仅原文块
    scope: QaScope = "both"


class CitationItem(BaseModel):
    citationId: str
    paperId: str
    paperTitle: str
    sectionId: str
    sectionTitle: str
    pageNumber: int | None = None
    quote: str


class AskPaperResult(BaseModel):
    conversationId: str
    messageId: str
    paperId: str
    answer: str
    createdAt: str
    citations: list[CitationItem]
    historyCount: int = 0
    answerMode: str = "agent"
