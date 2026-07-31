from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, ParseTask, Paper, PaperContent
from app.schema.papers import PaperUpsert
from app.service import parse_agent_runner
from app.service.papers import batch_upsert_papers
from app.service.parse_agent_runner import run_parse_agent_job
from app.service.parse_agent_runner import _ArxivHtmlTextParser, _persist_paper_content
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
            None,
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


def test_ar5iv_html_parser_keeps_sections_and_skips_scripts() -> None:
    parser = _ArxivHtmlTextParser()
    parser.feed(
        """
        <html><body>
          <h2>3 Experiments</h2>
          <p>We evaluate the model on a benchmark and report accuracy improvements.</p>
          <script>do not include this content</script>
        </body></html>
        """
    )
    text = parser.text()
    assert "[page 1] [experiments]" in text
    assert "accuracy improvements" in text
    assert "do not include" not in text


def test_persist_paper_content_records_path_checksum_and_mime(tmp_path) -> None:
    engine = create_engine_for(Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'content.db'}"))
    Base.metadata.create_all(engine)
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-test")

    with Session(engine) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="stored-paper", title="Stored Paper")],
        ).items[0].paper_id
        paper = session.get(Paper, paper_id)
        _persist_paper_content(session, paper, str(source))
        saved = session.get(PaperContent, paper_id)

    assert saved.storage_path == str(source)
    assert saved.mime_type == "application/pdf"
    assert saved.checksum
    assert saved.downloaded_at is not None
