from datetime import datetime, timezone
from dataclasses import dataclass
from uuid import uuid4
from typing import Any

from app.agents import QaAgent
from app.agents.llm_client import LlmError
from app.core.config import get_settings
from app.repository.paper import get_paper, get_paper_summary
from app.schema.qa import AskPaperRequest, AskPaperResult
from app.service.qa_citations import select_relevant_chunk_ids


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    citation_ids: list[str]
    refused: bool = False


def answer_with_agent(
    *,
    question: str,
    evidence: list[dict[str, Any]],
    history: list[dict[str, str]] | None = None,
    title: str = "",
    settings=None,
) -> GroundedAnswer:
    """Use the grounded Agent path without an extractive fallback."""
    settings = settings or get_settings()
    if not settings.qa_agent_ready:
        raise LlmError("问答 Agent 未配置或未启用")
    generated = QaAgent(settings).run(title=title, question=question, evidence=evidence, history=history)
    if generated.refuse:
        return GroundedAnswer(answer=generated.answer, citation_ids=[], refused=True)
    selected_ids = select_relevant_chunk_ids(
        answer=generated.answer,
        evidence=evidence,
        preferred_ids=generated.citation_ids,
    )
    if not selected_ids:
        return GroundedAnswer(answer=generated.answer, citation_ids=[], refused=True)
    return GroundedAnswer(answer=generated.answer, citation_ids=selected_ids)


def ask_paper(paper_id: str, request: AskPaperRequest) -> AskPaperResult:
    paper = get_paper(paper_id)
    summary = get_paper_summary(paper_id)
    if not paper or not summary:
        raise KeyError(paper_id)

    question = request.question.strip()
    evidence = [
        {"chunk_id": "mock-summary", "page_no": 1, "section": "Abstract", "content": summary["summary"]},
        *[
            {"chunk_id": f"mock-method-{index}", "page_no": 1, "section": "Method", "content": item["description"]}
            for index, item in enumerate(summary.get("methods", []), start=1)
        ],
        *[
            {"chunk_id": f"mock-limit-{index}", "page_no": 1, "section": "Limitations", "content": item}
            for index, item in enumerate(summary.get("limitations", []), start=1)
        ],
    ]
    grounded = answer_with_agent(
        question=question,
        evidence=evidence,
        history=[item.model_dump() for item in request.history],
        title=paper["title"],
    )
    if grounded.refused or not grounded.citation_ids:
        raise LlmError("QA Agent 无法基于证据回答该问题")
    citation_ids = set(grounded.citation_ids)
    selected = [item for item in evidence if item["chunk_id"] in citation_ids]
    if not selected:
        raise LlmError("QA Agent 返回的引用无法匹配证据")

    now = datetime.now(timezone.utc).isoformat()
    return AskPaperResult(
        conversationId=request.conversationId or f"conversation-{paper_id}-{uuid4()}",
        messageId=f"assistant-{uuid4()}",
        paperId=paper_id,
        answer=grounded.answer,
        createdAt=now,
        citations=[
            {
                "citationId": f"citation-{uuid4()}",
                "paperId": paper_id,
                "paperTitle": paper["title"],
                "sectionId": item["chunk_id"],
                "sectionTitle": item["section"] or "原文",
                "pageNumber": item["page_no"],
                "quote": item["content"],
            }
            for item in selected
        ],
        historyCount=len(request.history),
    )
