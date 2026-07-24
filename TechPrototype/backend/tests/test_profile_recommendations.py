from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, Paper, StructuredResult
from app.schema.papers import PaperUpsert, UserActionInput, UserProfileUpdate
from app.service.admin import admin_overview
from app.service.learning import create_action
from app.service.papers import batch_upsert_papers
from app.service.profile import get_dictionary, get_profile, update_profile
from app.service.recommendations import profile_recommendations


def test_profile_dictionary_recommendation_and_admin_data(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'profile.db'}")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="profile-paper", title="Profile Paper", primary_category="cs.CL")],
        ).items[0]
        session.execute(
            StructuredResult.__table__.insert().values(
                paper_id=paper.paper_id,
                result_type="concepts",
                version=1,
                content_json={"items": [{"name": "Attention", "description": "关注序列依赖。"}]},
                source_locator={},
            )
        )
        session.commit()
        record = session.get(Paper, paper.paper_id)
        record.ingest_status = "qa_ready"
        record.chunk_count = 1
        session.commit()

        profile = update_profile(session, "student", UserProfileUpdate(persona="工程", topics=["cs.CL"], preferences={"code": True}))
        assert profile.persona == "工程"
        assert get_profile(session, "student").topics == ["cs.CL"]

        # Personal dictionary requires user interaction with a parsed paper
        assert get_dictionary(session, "student") == []

        create_action(session, UserActionInput(user_id="student", paper_id=paper.paper_id, action_type="favorite", payload_json={"favorite": True}))

        dictionary = get_dictionary(session, "student")
        assert dictionary[0].term == "Attention"
        assert dictionary[0].paper_ids == [paper.paper_id]
        recommendations = profile_recommendations(session, user_id="student", limit=3)
        assert recommendations == []
        overview = admin_overview(session, settings)
        assert overview["metrics"]["papers"] == 1


def test_dictionary_uses_parsed_status_and_skips_fallback_noise(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'dict2.db'}")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="dict-parsed", title="Parsed Only", primary_category="cs.LG")],
        ).items[0]
        session.execute(
            StructuredResult.__table__.insert().values(
                paper_id=paper.paper_id,
                result_type="concepts",
                version=1,
                content_json={
                    "items": [
                        {"name": "核心贡献", "description": "占位"},
                        {"name": "LoRA", "description": "低秩适配微调方法"},
                    ]
                },
                source_locator={},
            )
        )
        record = session.get(Paper, paper.paper_id)
        record.ingest_status = "parsed"  # completed parse without qa chunks
        session.commit()

        create_action(
            session,
            UserActionInput(user_id="reader", paper_id=paper.paper_id, action_type="reading_history", payload_json={}),
        )
        dictionary = get_dictionary(session, "reader")
        assert [item.term for item in dictionary] == ["LoRA"]
