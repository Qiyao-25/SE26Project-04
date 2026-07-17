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
    fallback: str,
    history: list[dict[str, str]] | None = None,
    title: str = "",
    settings=None,
) -> GroundedAnswer:
    """Use one grounded-Agent path for database and sample-paper QA."""
    fallback_ids = [str(item.get("chunk_id")) for item in evidence if item.get("chunk_id")]
    settings = settings or get_settings()
    if not settings.qa_agent_ready:
        return GroundedAnswer(answer=fallback, citation_ids=fallback_ids)
    try:
        generated = QaAgent(settings).run(title=title, question=question, evidence=evidence, history=history)
        selected_ids = select_relevant_chunk_ids(
            answer=generated.answer,
            evidence=evidence,
            preferred_ids=generated.citation_ids,
        )
        if generated.refuse:
            return GroundedAnswer(answer=generated.answer, citation_ids=[], refused=True)
        if not selected_ids:
            raise LlmError("Agent answer has no supporting evidence")
        return GroundedAnswer(answer=generated.answer, citation_ids=selected_ids)
    except LlmError:
        return GroundedAnswer(answer=fallback, citation_ids=fallback_ids)


def ask_paper(paper_id: str, request: AskPaperRequest) -> AskPaperResult:
    paper = get_paper(paper_id)
    summary = get_paper_summary(paper_id)
    if not paper or not summary:
        raise KeyError(paper_id)

    question = request.question.strip()
    question_lower = question.lower()

    if any(keyword in question_lower for keyword in ["局限", "limit"]):
        answer = "该论文当前样例解析出的局限性包括：" + "；".join(summary["limitations"])
        section_title = "Limitations"
        quote = summary["limitations"][0]
    elif any(keyword in question_lower for keyword in ["方法", "method", "怎么做"]):
        answer = "论文的方法流程包括：" + "；".join(
            f"{item['title']}：{item['description']}" for item in summary["methods"]
        )
        section_title = "Method"
        quote = summary["methods"][1]["description"]
    else:
        answer = f"《{paper['title']}》的核心内容是：{summary['summary']}"
        section_title = "Abstract"
        quote = paper["abstract"]

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
        fallback=answer,
        history=[item.model_dump() for item in request.history],
        title=paper["title"],
    )
    citation_ids = set(grounded.citation_ids)
    selected = [item for item in evidence if item["chunk_id"] in citation_ids]
    if not selected and not grounded.refused:
        selected = [evidence[0]]

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
                "sectionTitle": item["section"] or section_title,
                "pageNumber": item["page_no"],
                "quote": item["content"],
            }
            for item in selected
        ],
        historyCount=len(request.history),
    )
