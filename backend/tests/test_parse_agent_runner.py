from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, ParseTask, Paper
from app.schema.papers import PaperUpsert
from app.service import parse_agent_runner
from app.service.papers import batch_upsert_papers
from app.service.parse_agent_runner import run_parse_agent_job
from app.service.tasks import create_task


def test_parse_job_completes_with_local_fallback(tmp_path, monkeypatch) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'parse.db'}",
        parse_agent_enabled=False,
    )
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        parse_agent_runner,
        "_extract_paper_text",
        lambda paper, settings: (
            "[page 1] This paper proposes an attention model architecture. "
            "Experiments on a benchmark report improved accuracy.",
            1,
            "test",
        ),
    )

    with Session(engine) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="fallback-paper", title="Fallback Paper", abstract="A paper abstract.")],
        ).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "fallback-task")

    run_parse_agent_job(engine, task.task_id, settings)

    with Session(engine) as session:
        saved_task = session.get(ParseTask, task.task_id)
        saved_paper = session.get(Paper, paper_id)
        assert saved_task.status == "succeeded"
        assert saved_task.stage == "completed"
        assert saved_paper.ingest_status == "qa_ready"
        assert saved_paper.chunk_count > 0
        result_types = {item.result_type for item in saved_paper.structured_results}
        assert {"summary", "concepts", "methods", "experiments", "limitations", "validation"} <= result_types
