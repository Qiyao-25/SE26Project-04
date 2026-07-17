from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import PaperUpsert, ParseRequest, StructuredResultBatch, StructuredResultInput, TaskUpdate
from app.service.papers import batch_upsert_papers, get_wiki
from app.service.tasks import create_task, get_task, list_tasks, save_results, update_task
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
        assert forced.task_id == first.task_id
        queued = list_tasks(session, status="queued", limit=10)
        assert [task.task_id for task in queued] == [first.task_id]
        update_task(session, first.task_id, TaskUpdate(status="running"))
        assert list_tasks(session, status="queued", limit=10) == []
