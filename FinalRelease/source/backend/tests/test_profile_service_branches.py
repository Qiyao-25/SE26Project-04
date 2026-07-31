"""Profile service branch tests."""

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, StructuredResult
from app.schema.papers import PaperUpsert, UserActionInput, UserProfileUpdate
from app.service.learning import create_action
from app.service.papers import batch_upsert_papers
from app.service.profile import get_dictionary, merge_auto_topics, sync_topics_from_behavior, update_profile


def _session(tmp_path) -> Session:
    engine = create_engine_for(Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'profile.db'}"))
    Base.metadata.create_all(engine)
    return Session(engine)


def test_merge_auto_topics_respects_exclusions() -> None:
    merged = merge_auto_topics(locked=["cs.CL"], auto=["cs.LG", "cs.CL"], excluded=["cs.LG"], limit=5)
    assert merged == ["cs.CL"]


def test_sync_topics_from_behavior(tmp_path) -> None:
    with _session(tmp_path) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="prof-cl", title="CL", primary_category="cs.CL")],
        ).items[0].paper_id
        create_action(
            session,
            UserActionInput(user_id="p1", paper_id=paper_id, action_type="favorite", payload_json={"favorite": True}),
        )
        profile = sync_topics_from_behavior(session, "p1")
        assert profile is not None
        assert "cs.CL" in profile.topics


def test_dictionary_with_structured_concepts(tmp_path) -> None:
    with _session(tmp_path) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="dict-paper", title="Dict Paper", ingest_status="qa_ready")],
        ).items[0].paper_id
        session.add(
            StructuredResult(
                paper_id=paper_id,
                result_type="concepts",
                version=1,
                content_json={"items": [{"name": "Transformer", "description": "sequence model"}]},
                source_locator={},
            )
        )
        session.commit()
        create_action(
            session,
            UserActionInput(user_id="p2", paper_id=paper_id, action_type="reading_history", payload_json={}),
        )
        update_profile(session, "p2", UserProfileUpdate(topics=["cs.CL"]))
        entries = get_dictionary(session, "p2")
        assert any(entry.term == "Transformer" for entry in entries)
