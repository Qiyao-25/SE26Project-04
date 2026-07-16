from copy import deepcopy

from app.data import PAPERS, PAPER_CONTENT, PAPER_SUMMARIES


def list_papers() -> list[dict]:
    return [deepcopy(item) for item in PAPERS.values()]


def get_paper(paper_id: str) -> dict | None:
    item = PAPERS.get(paper_id)
    return deepcopy(item) if item else None


def get_paper_content(paper_id: str) -> dict | None:
    item = PAPER_CONTENT.get(paper_id)
    return deepcopy(item) if item else None


def get_paper_summary(paper_id: str) -> dict | None:
    item = PAPER_SUMMARIES.get(paper_id)
    return deepcopy(item) if item else None
