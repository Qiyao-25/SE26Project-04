import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.model import Base, Paper, StructuredResult
from app.schema.papers import PaperUpsert, StructuredResultBatch, StructuredResultInput
from app.service.papers import batch_upsert_papers
from app.service.tasks import create_task, save_results


POSTGRES_URL = os.environ.get("PAPERMATE_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="set PAPERMATE_TEST_POSTGRES_URL to run PostgreSQL integration tests",
)


def test_postgres_transaction_json_and_constraints() -> None:
    assert POSTGRES_URL
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    arxiv_id = f"postgres-test-{uuid4().hex}"
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1

        with Session(engine) as session:
            paper_id = batch_upsert_papers(
                session,
                [PaperUpsert(arxiv_id=arxiv_id, title="PostgreSQL Integration Paper")],
            ).items[0].paper_id
            task, _ = create_task(session, paper_id, "full_parse", f"postgres-task-{uuid4().hex}")
            completed = save_results(
                session,
                task.task_id,
                StructuredResultBatch(
                    results=[
                        StructuredResultInput(
                            result_type="summary",
                            content_json={"summary": "transactional JSON"},
                            source_locator={"page": 1},
                        )
                    ]
                ),
            )
            assert completed.status == "succeeded"
            stored = session.scalar(
                select(StructuredResult).where(StructuredResult.paper_id == paper_id)
            )
            assert stored is not None
            assert stored.content_json["summary"] == "transactional JSON"
    finally:
        with Session(engine) as session:
            paper = session.scalar(select(Paper).where(Paper.arxiv_id == arxiv_id))
            if paper is not None:
                session.delete(paper)
                session.commit()
        engine.dispose()
