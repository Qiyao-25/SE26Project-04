from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, Paper, StructuredResult
from app.schema.papers import PaperUpsert, UserActionInput, UserProfileUpdate
from app.service.learning import create_action
from app.service.papers import batch_upsert_papers
from app.service.profile import update_profile
from app.service.recommendations import daily_picks, profile_recommendations, score_paper


def _make_session(tmp_path, name: str):
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / name}")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_profile_excludes_favorites_but_ranks_related(tmp_path) -> None:
    with _make_session(tmp_path, "reco1.db") as session:
        items = batch_upsert_papers(
            session,
            [
                PaperUpsert(arxiv_id="fav-1", title="Favorite CL Paper", primary_category="cs.CL", abstract="nlp"),
                PaperUpsert(
                    arxiv_id="cand-1",
                    title="Attention for Translation",
                    primary_category="cs.CL",
                    abstract="sequence attention transformer",
                ),
                PaperUpsert(
                    arxiv_id="noise-1",
                    title="Quantum Optics",
                    primary_category="physics.optics",
                    abstract="laser cavity",
                ),
            ],
        ).items
        fav_id, cand_id, noise_id = [item.paper_id for item in items]
        for paper_id, status in ((fav_id, "qa_ready"), (cand_id, "qa_ready"), (noise_id, "metadata_only")):
            record = session.get(Paper, paper_id)
            record.ingest_status = status
            record.chunk_count = 1 if status == "qa_ready" else 0
        session.commit()

        update_profile(session, "student", UserProfileUpdate(persona="研究", topics=["cs.CL"], preferences={"code": False}))
        create_action(
            session,
            UserActionInput(user_id="student", paper_id=fav_id, action_type="favorite", payload_json={"favorite": True}),
        )

        recommendations = profile_recommendations(session, user_id="student", limit=3)
        ids = [item.paper_id for item in recommendations]
        assert fav_id not in ids
        assert cand_id in ids
        assert recommendations[0].recommend_source == "profile"


def test_engineering_persona_prefers_code_signal(tmp_path) -> None:
    with _make_session(tmp_path, "reco2.db") as session:
        paper_code = Paper(
            arxiv_id="code-1",
            title="Efficient Inference Toolkit",
            abstract="Open-source implementation available at github.com/example/repo",
            primary_category="cs.LG",
            ingest_status="parsed",
            published_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        paper_theory = Paper(
            arxiv_id="theory-1",
            title="Theoretical Bounds of Learning",
            abstract="We prove generalization bounds without releasing code.",
            primary_category="cs.LG",
            ingest_status="parsed",
            published_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        session.add_all([paper_code, paper_theory])
        session.commit()

        score_eng_code, _ = score_paper(
            paper_code,
            ["cs.LG"],
            prefer_code=True,
            persona="工程",
        )
        score_eng_theory, _ = score_paper(
            paper_theory,
            ["cs.LG"],
            prefer_code=True,
            persona="工程",
        )
        assert score_eng_code > score_eng_theory

        score_teach_survey, _ = score_paper(
            Paper(
                arxiv_id="survey-1",
                title="A Survey of Transformers",
                abstract="tutorial overview",
                primary_category="cs.CL",
                ingest_status="qa_ready",
            ),
            ["cs.CL"],
            prefer_code=False,
            persona="教学",
        )
        score_eng_survey, _ = score_paper(
            Paper(
                arxiv_id="survey-2",
                title="A Survey of Transformers",
                abstract="tutorial overview",
                primary_category="cs.CL",
                ingest_status="qa_ready",
            ),
            ["cs.CL"],
            prefer_code=False,
            persona="工程",
        )
        assert score_teach_survey >= score_eng_survey


def test_daily_picks_prefer_quality_and_diversity(tmp_path) -> None:
    with _make_session(tmp_path, "reco3.db") as session:
        now = datetime.now(timezone.utc)
        papers = [
            Paper(
                arxiv_id=f"d-{index}",
                title=f"Paper {index}",
                abstract="x" * 800,
                primary_category=category,
                ingest_status=status,
                published_at=now - timedelta(days=days),
            )
            for index, (category, status, days) in enumerate(
                [
                    ("cs.CL", "qa_ready", 5),
                    ("cs.CL", "metadata_only", 5),
                    ("cs.LG", "qa_ready", 8),
                    ("math.OC", "qa_ready", 12),
                    ("cs.CV", "parsed", 3),
                ]
            )
        ]
        session.add_all(papers)
        session.commit()

        picks = daily_picks(session, limit=3)
        assert len(picks) == 3
        assert all(item.recommend_source == "daily" for item in picks)
        categories = {item.primary_category for item in picks}
        assert len(categories) >= 2
