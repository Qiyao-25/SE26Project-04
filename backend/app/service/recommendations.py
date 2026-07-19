from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import Paper, UserAction
from app.repository.papers import list_papers
from app.schema.papers import PaperItem
from app.service.papers import to_item
from app.service.profile import get_profile


def daily_picks(session: Session, limit: int = 3) -> list[PaperItem]:
    papers, _ = list_papers(
        session, keyword=None, keywords=None, author=None, category=None,
        published_from=None, published_to=None, page=1, page_size=min(limit, 50),
    )
    return [to_item(paper) for paper in papers[:limit]]


def profile_recommendations(
    session: Session,
    *,
    user_id: str,
    persona: str | None = None,
    topics: list[str] | None = None,
    limit: int = 3,
    exclude_ids: list[int] | None = None,
) -> list[PaperItem]:
    profile = get_profile(session, user_id)
    wanted_topics = topics or profile.topics
    excluded = set(exclude_ids or [])
    excluded.update(
        session.scalars(
            select(UserAction.paper_id).where(
                UserAction.user_id == user_id,
                UserAction.action_type == "favorite",
            )
        ).all()
    )
    papers, _ = list_papers(
        session, keyword=None, keywords=wanted_topics or None, author=None,
        category=None, published_from=None, published_to=None, page=1, page_size=50,
    )
    if not papers:
        papers, _ = list_papers(
            session, keyword=None, keywords=None, author=None, category=None,
            published_from=None, published_to=None, page=1, page_size=50,
        )
    items = [to_item(paper) for paper in papers if paper.id not in excluded]
    return items[:limit]
