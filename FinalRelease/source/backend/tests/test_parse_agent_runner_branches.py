"""Branch coverage for parse agent runner."""

from sqlalchemy.orm import Session

from app.agents.llm_client import LlmError
from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, ParseTask, Paper
from app.schema.papers import PaperUpsert, TaskUpdate
from app.service import parse_agent_runner
from app.service.papers import batch_upsert_papers
from app.service.parse_agent_runner import (
    _execute,
    _fail,
    _text_to_chunks,
    run_parse_agent_job,
)
from app.service.tasks import claim_task, create_task, save_results, update_task
from app.schema.papers import StructuredResultBatch, StructuredResultInput


def _engine(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'parse-br.db'}",
        parse_agent_enabled=True,
        llm_api_key="test-key",
        llm_model="test-model",
    )
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    return engine, settings


def test_run_parse_agent_job_skips_completed_task(tmp_path) -> None:
    engine, settings = _engine(tmp_path)
    with Session(engine) as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="skip-paper", title="Skip")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "skip-task")
        update_task(session, task.task_id, TaskUpdate(status="running"))
        save_results(
            session,
            task.task_id,
            StructuredResultBatch(results=[StructuredResultInput(result_type="summary", content_json={"summary": "ok"})]),
        )
    run_parse_agent_job(engine, task.task_id, settings)
    with Session(engine) as session:
        saved = session.get(ParseTask, task.task_id)
        assert saved is not None
        assert saved.status == "succeeded"


def test_execute_content_empty_and_blank_body(tmp_path, monkeypatch) -> None:
    engine, settings = _engine(tmp_path)
    with Session(engine) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="empty-body", title="Empty", abstract="only abstract")],
        ).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "empty-task")
        claimed = claim_task(session, "worker-a")
        assert claimed is not None and claimed.lease_token

        monkeypatch.setattr(
            parse_agent_runner,
            "_extract_paper_text",
            lambda paper, settings: ("", 0, "abstract_fallback", None),
        )
        _execute(session, task.task_id, settings, lease_token=claimed.lease_token)
        paper = session.get(Paper, paper_id)
        assert paper is not None
        assert paper.deleted_at is not None

        paper_id2 = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="blank-body", title="Blank", abstract="abstract")],
        ).items[0].paper_id
        task2, _ = create_task(session, paper_id2, "full_parse", "blank-task")
        claimed2 = claim_task(session, "worker-b")
        assert claimed2 is not None and claimed2.lease_token
        monkeypatch.setattr(
            parse_agent_runner,
            "_extract_paper_text",
            lambda paper, settings: ("   ", 1, "pdf", None),
        )
        _execute(session, task2.task_id, settings, lease_token=claimed2.lease_token)
        failed = session.get(ParseTask, task2.task_id)
        assert failed is not None
        assert failed.error_code == "PARSE_FAILED"


def test_execute_paper_not_found(tmp_path, monkeypatch) -> None:
    engine, settings = _engine(tmp_path)
    with Session(engine) as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="gone-paper", title="Gone")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "gone-task")
        claimed = claim_task(session, "worker-c")
        assert claimed is not None and claimed.lease_token
        original_get = session.get

        def fake_get(model, key):
            if model is Paper:
                return None
            return original_get(model, key)

        monkeypatch.setattr(session, "get", fake_get)
        _execute(session, task.task_id, settings, lease_token=claimed.lease_token)
        saved = session.get(ParseTask, task.task_id)
        assert saved is not None
        assert saved.error_code == "PAPER_NOT_FOUND"


def test_execute_agent_fallbacks_and_empty_chunks(tmp_path, monkeypatch) -> None:
    engine, settings = _engine(tmp_path)
    body = "[page 1] This paper proposes an attention model evaluated on benchmarks with strong accuracy."

    with Session(engine) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="fallback-paper", title="Fallback", abstract="abs")],
        ).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "fallback-task")
        claimed = claim_task(session, "worker-d")
        assert claimed is not None and claimed.lease_token

        monkeypatch.setattr(
            parse_agent_runner,
            "_extract_paper_text",
            lambda paper, settings: (body, 1, "pdf", None),
        )

        class BoomSummarize:
            def run(self, **kwargs):
                raise LlmError("summarize down")

        class BoomGraph:
            def run(self, **kwargs):
                raise RuntimeError("graph down")

        class BoomValidate:
            def validate_wiki(self, **kwargs):
                raise RuntimeError("validate down")

        monkeypatch.setattr(parse_agent_runner, "SummarizeAgent", lambda settings: BoomSummarize())
        monkeypatch.setattr(parse_agent_runner, "GraphAgent", lambda settings: BoomGraph())
        monkeypatch.setattr(parse_agent_runner, "ContentValidationAgent", lambda: BoomValidate())
        monkeypatch.setattr(parse_agent_runner, "_text_to_chunks", lambda text, max_chunks=80: [])

        _execute(session, task.task_id, settings, lease_token=claimed.lease_token)
        saved_task = session.get(ParseTask, task.task_id)
        saved_paper = session.get(Paper, paper_id)
        assert saved_task is not None and saved_task.status == "succeeded"
        assert saved_paper is not None
        assert saved_paper.ingest_status == "qa_ready"
        assert saved_paper.chunk_count >= 1


def test_text_to_chunks_empty_and_fail_missing_task(tmp_path) -> None:
    assert _text_to_chunks("") == []
    assert _text_to_chunks("   ") == []
    engine, _settings = _engine(tmp_path)
    with Session(engine) as session:
        _fail(session, 99999, "WORKER_ERROR")
        assert session.get(ParseTask, 99999) is None
