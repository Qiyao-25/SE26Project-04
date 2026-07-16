from datetime import datetime, timezone
from uuid import uuid4

from app.repository.paper import get_paper, get_paper_summary
from app.schema.qa import AskPaperRequest, AskPaperResult


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

    now = datetime.now(timezone.utc).isoformat()
    return AskPaperResult(
        conversationId=request.conversationId or f"conversation-{paper_id}-{uuid4()}",
        messageId=f"assistant-{uuid4()}",
        paperId=paper_id,
        answer=answer,
        createdAt=now,
        citations=[
            {
                "citationId": f"citation-{uuid4()}",
                "paperId": paper_id,
                "paperTitle": paper["title"],
                "sectionId": section_title.lower(),
                "sectionTitle": section_title,
                "pageNumber": 1,
                "quote": quote,
            }
        ],
        historyCount=len(request.history),
    )
