"""Agent and end-to-end acceptance scenarios for ``python -m harness``."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.llm_client import use_llm_client
from app.agents.qa_agent import QaAgent
from app.agents.summarize_agent import SummarizeAgent
from app.core.config import Settings, get_settings
from app.core.database import create_engine_for
from app.model import Base, Paper, ParseTask, StructuredResult
from app.service.parse_agent_runner import run_parse_agent_job
from app.service.tasks import create_task

from .llm_stub import HarnessLlmStub


FIXTURE_BODY = (
    "The paper proposes a self-attention architecture for sequence modeling. "
    "The encoder and decoder use multi-head attention and feed-forward networks. "
    "Experiments on benchmark translation tasks show improved performance."
)


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    ok: bool
    checks: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"scenario": self.name, "ok": self.ok, "checks": self.checks}


def run_agent_scenario(*, live: bool = False) -> ScenarioResult:
    """Validate structured-summary and grounded-QA Agent contracts."""
    settings = _settings(live=live)
    stub = HarnessLlmStub()
    client_context = nullcontext() if live else use_llm_client(stub)
    with client_context:
        wiki = SummarizeAgent(settings).run(
            title="Harness Paper",
            abstract="A paper about self-attention.",
            body_text=FIXTURE_BODY,
            arxiv_id="harness-paper",
        )
        grounded = QaAgent(settings).run(
            title="Harness Paper",
            question="这篇论文提出了什么方法？",
            evidence=[
                {
                    "chunk_id": "harness-c1",
                    "page_no": 1,
                    "section": "method",
                    "content": FIXTURE_BODY,
                }
            ],
        )

    checks = {
        "summary_present": bool(wiki.summary.strip()),
        "structured_fields_present": all(
            bool(getattr(wiki, field))
            for field in ("concepts", "methods", "experiments", "limitations")
        ),
        "qa_answer_present": bool(grounded.answer.strip()),
        "qa_citation_is_grounded": grounded.citation_ids == ["harness-c1"],
        "stub_calls": len(stub.calls) if not live else None,
    }
    return ScenarioResult("agent", all(checks[key] for key in checks if key != "stub_calls"), checks)


def run_qa_scenario(*, live: bool = False) -> ScenarioResult:
    """Validate that QA returns a supported answer and a real evidence ID."""
    settings = _settings(live=live)
    stub = HarnessLlmStub()
    client_context = nullcontext() if live else use_llm_client(stub)
    with client_context:
        grounded = QaAgent(settings).run(
            title="Harness Paper",
            question="这篇论文提出了什么方法？",
            evidence=[
                {
                    "chunk_id": "harness-c1",
                    "page_no": 1,
                    "section": "method",
                    "content": FIXTURE_BODY,
                }
            ],
        )
    checks = {
        "answer_present": bool(grounded.answer.strip()),
        "not_refused": not grounded.refuse,
        "citation_from_evidence": grounded.citation_ids == ["harness-c1"],
    }
    return ScenarioResult("qa", all(checks.values()), checks)


def run_parse_scenario(*, live: bool = False) -> ScenarioResult:
    """Run the real parse runner against a local paper fixture."""
    settings = _settings(live=live)
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    stub = HarnessLlmStub()
    client_context = nullcontext() if live else use_llm_client(stub)

    with Session(engine) as session:
        paper = Paper(
            arxiv_id="harness-parse-paper",
            title="Harness Parse Paper",
            abstract="A paper about self-attention.",
            primary_category="cs.CL",
            ingest_status="metadata_only",
        )
        session.add(paper)
        session.commit()
        paper_id = paper.id
        task, _created = create_task(session, paper_id, "full_parse", "harness-parse-task")

    def extract_fixture(_paper: Paper, _settings: Settings) -> tuple[str, int, str, str | None]:
        return FIXTURE_BODY, 1, "harness_fixture", None

    with client_context:
        run_parse_agent_job(
            engine,
            task.task_id,
            settings,
            text_extractor=extract_fixture,
        )

    with Session(engine) as session:
        saved_task = session.get(ParseTask, task.task_id)
        saved_paper = session.get(Paper, paper_id)
        result_types = {
            item.result_type
            for item in session.query(StructuredResult).filter_by(paper_id=paper_id).all()
        }
        checks = {
            "task_succeeded": bool(saved_task and saved_task.status == "succeeded"),
            "completed_stage": bool(saved_task and saved_task.stage == "completed"),
            "paper_qa_ready": bool(saved_paper and saved_paper.ingest_status == "qa_ready"),
            "chunks_persisted": bool(saved_paper and saved_paper.chunk_count > 0),
            "summary_results_persisted": {"summary", "concepts", "methods"}.issubset(result_types),
            "graph_results_persisted": {"kg_graph", "topic_lineage"}.issubset(result_types),
        }
    engine.dispose()
    return ScenarioResult("parse", all(checks.values()), checks)


def run_e2e_scenario(*, live: bool = False) -> ScenarioResult:
    """Run the local parse and grounded-QA acceptance scenarios together."""
    parse_result = run_parse_scenario(live=live)
    qa_result = run_qa_scenario(live=live)
    checks = {
        "parse": parse_result.to_dict(),
        "qa": qa_result.to_dict(),
    }
    return ScenarioResult("e2e", parse_result.ok and qa_result.ok, checks)


def _settings(*, live: bool) -> Settings:
    if live:
        settings = get_settings()
        return settings.model_copy(
            update={
                "environment": "test",
                "database_url": "sqlite:///:memory:",
                "parse_scheduler_enabled": False,
                "crawl_enabled": False,
            }
        )
    return Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        llm_api_key="harness-key",
        llm_model="harness-model",
        parse_agent_enabled=True,
        qa_agent_enabled=True,
        graph_agent_enabled=True,
        parse_scheduler_enabled=False,
    )


def dumps_result(result: ScenarioResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


__all__ = [
    "ScenarioResult",
    "dumps_result",
    "run_agent_scenario",
    "run_e2e_scenario",
    "run_parse_scenario",
    "run_qa_scenario",
]
