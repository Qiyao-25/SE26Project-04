from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: str
    content: str


class AskPaperRequest(BaseModel):
    conversationId: str | None = None
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessage] = []


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
