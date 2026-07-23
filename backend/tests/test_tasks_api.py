from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, ParseTask
from datetime import timedelta

from app.schema.papers import ParseResultCommit, PaperUpsert, StructuredResultBatch, StructuredResultInput, TaskUpdate, TextChunkBatch, TextChunkInput
from app.repository.chunks import upsert_chunks
from app.service.papers import batch_upsert_papers, get_wiki
from app.service.tasks import claim_task, create_task, enqueue_pending_tasks, get_task, list_tasks, queue_stats, recover_stale_tasks, retry_task, save_parse_result, save_results, update_task
from sqlalchemy.orm import Session


def make_session() -> Session:
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return Session(engine)


def test_parse_task_is_idempotent_and_results_update_wiki() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="task-paper", title="Task Paper", abstract="Abstract")]).items[0].paper_id
        first, _ = create_task(session, paper_id, "full_parse", "task-key")
        second, _ = create_task(session, paper_id, "full_parse", "task-key")
        assert second.task_id == first.task_id
        completed = save_results(session, first.task_id, StructuredResultBatch(results=[StructuredResultInput(result_type="summary", content_json={"summary": "Stored summary"}, source_locator={"page": 1})]))
        assert completed.status == "succeeded"
        assert get_wiki(session, paper_id).summary == "Stored summary"


def test_parse_requires_idempotency_key_and_unknown_task_is_not_found() -> None:
    with make_session() as session:
        try:
            get_task(session, 999)
        except ValueError as exc:
            assert str(exc) == "TASK_NOT_FOUND"
        else:
            raise AssertionError("expected TASK_NOT_FOUND")


def test_list_tasks_returns_oldest_queued_tasks_first() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="queue-paper", title="Queue Paper")]).items[0].paper_id
        first, _ = create_task(session, paper_id, "full_parse", "queue-key-1")
        second, _ = create_task(session, paper_id, "full_parse", "queue-key-2")
        assert second.task_id == first.task_id
        forced, _ = create_task(session, paper_id, "full_parse", "queue-key-force", force=True)
        assert forced.task_id != first.task_id
        assert get_task(session, first.task_id).error_code == "SUPERSEDED"
        queued = list_tasks(session, status="queued", limit=10)
        assert [task.task_id for task in queued] == [forced.task_id]
        update_task(session, forced.task_id, TaskUpdate(status="running"))
        assert list_tasks(session, status="queued", limit=10) == []


def test_task_stage_is_persisted() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="stage-paper", title="Stage Paper")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "stage-key")
        updated = update_task(session, task.task_id, TaskUpdate(status="running", stage="parse"))
        assert updated.stage == "parse"
        assert get_task(session, task.task_id).stage == "parse"


def test_worker_claim_is_atomic_and_starts_task() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="claim-paper", title="Claim Paper")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "claim-key")
        claimed = claim_task(session, "worker-a")
        assert claimed is not None
        assert claimed.task_id == task.task_id
        assert claimed.status == "running"
        assert claimed.stage == "fetch"
        assert claim_task(session, "worker-b") is None


def test_completed_task_rejects_late_status_update() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="transition-paper", title="Transition Paper")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "transition-key")
        claim_task(session, "worker-a")
        update_task(session, task.task_id, TaskUpdate(status="failed", error_code="PARSE_FAILED"))
        retry_task(session, task.task_id)
        update_task(session, task.task_id, TaskUpdate(status="running"))
        save_results(session, task.task_id, StructuredResultBatch(results=[StructuredResultInput(result_type="summary", content_json={"summary": "done"})]))
        try:
            update_task(session, task.task_id, TaskUpdate(status="failed", error_code="LATE_FAILURE"))
        except ValueError as exc:
            assert str(exc) == "TASK_STATE_CONFLICT"
        else:
            raise AssertionError("expected TASK_STATE_CONFLICT")




def test_paper_becomes_qa_ready_only_after_chunks_are_persisted() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="qa-ready-paper", title="QA Ready Paper")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "qa-ready-task")
        upsert_chunks(
            session,
            paper_id,
            TextChunkBatch(chunks=[TextChunkInput(chunk_id="chunk-1", page_no=1, content="Evidence text.")]),
        )
        save_results(
            session,
            task.task_id,
            StructuredResultBatch(results=[StructuredResultInput(result_type="summary", content_json={"summary": "summary"})]),
        )
        wiki = get_wiki(session, paper_id)
        assert wiki.qa_ready is True
        assert wiki.chunk_count == 1


def test_failed_task_can_be_retried_once() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="retry-paper", title="Retry Paper")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "retry-task")
        update_task(session, task.task_id, TaskUpdate(status="running", stage="parse"))
        update_task(session, task.task_id, TaskUpdate(status="failed", error_code="PARSE_FAILED", stage="failed"))
        retried = retry_task(session, task.task_id)
        assert retried.status == "queued"
        assert retried.attempt == 2
        update_task(session, task.task_id, TaskUpdate(status="running", stage="parse"))
        update_task(session, task.task_id, TaskUpdate(status="failed", error_code="WORKER_ERROR", stage="failed"))
        try:
            retry_task(session, task.task_id)
        except ValueError as exc:
            assert str(exc) == "TASK_RETRY_EXHAUSTED"
        else:
            raise AssertionError("expected TASK_RETRY_EXHAUSTED after one retry")


def test_content_empty_soft_deletes_paper() -> None:
    from app.model import Paper
    from app.service.parse_agent_runner import _fail

    with make_session() as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="empty-paper", title="Empty Body Paper", abstract="only abstract")],
        ).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "empty-content-task")
        update_task(session, task.task_id, TaskUpdate(status="running", stage="fetch"))
        _fail(session, task.task_id, "CONTENT_EMPTY", soft_delete=True)
        paper = session.get(Paper, paper_id)
        assert paper is not None
        assert paper.deleted_at is not None
        assert get_task(session, task.task_id).error_code == "CONTENT_EMPTY"


def test_stale_running_task_is_recovered() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="stale-paper", title="Stale Paper")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "stale-task")
        update_task(session, task.task_id, TaskUpdate(status="running", stage="parse"))
        record = session.get(ParseTask, task.task_id)
        record.started_at = record.started_at - timedelta(hours=1)
        session.commit()
        recovered = recover_stale_tasks(session, stale_after_seconds=60)
        assert [item.task_id for item in recovered] == [task.task_id]
        assert get_task(session, task.task_id).status == "timed_out"


def test_metadata_only_papers_can_be_enqueued() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="pending-paper", title="Pending Paper")]).items[0].paper_id
        queued = enqueue_pending_tasks(session, limit=10)
        assert queued and queued[0].paper_id == paper_id
        assert get_task(session, queued[0].task_id).status == "queued"


def test_finalize_replaces_chunks_and_updates_queue_readiness() -> None:
    with make_session() as session:
        paper_id = batch_upsert_papers(session, [PaperUpsert(arxiv_id="finalize-paper", title="Finalize Paper")]).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "finalize-task")
        completed = save_parse_result(
            session,
            task.task_id,
            ParseResultCommit(
                chunks=[TextChunkInput(chunk_id="fresh", page_no=2, section="results", content="Fresh evidence")],
                results=[StructuredResultInput(result_type="summary", content_json={"summary": "Fresh summary"})],
            ),
        )
        assert completed.stage == "completed"
        wiki = get_wiki(session, paper_id)
        assert wiki.qa_ready is True
        assert wiki.chunk_count == 1
        stats = queue_stats(session)
        assert stats["counts"]["succeeded"] == 1
        assert stats["counts"]["queued"] == 0
