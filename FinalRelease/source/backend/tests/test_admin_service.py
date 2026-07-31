"""Unit tests for admin service helpers and mutations."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, Paper, User, UserAction, UserProfile
from app.schema.papers import PaperUpsert, TaskUpdate
from app.service.admin import (
    admin_overview,
    admin_quality,
    admin_tasks,
    admin_users,
    delete_user,
    explain_parse_failure,
    update_user_status,
)
from app.service.auth import hash_password
from app.service.papers import batch_upsert_papers
from app.service.tasks import create_task, update_task


def _session(tmp_path, name: str = "admin.db") -> Session:
    engine = create_engine_for(Settings(environment="test", database_url=f"sqlite:///{tmp_path / name}"))
    Base.metadata.create_all(engine)
    return Session(engine)


def test_explain_parse_failure_all_branches() -> None:
    assert explain_parse_failure(error_code="CONTENT_EMPTY", stage=None, status=None)["agent"] == "抓取 Agent"
    assert explain_parse_failure(error_code="PARSE_FAILED", stage=None, status=None)["stage_label"] == "抓取 / 正文提取"
    assert explain_parse_failure(error_code="PAPER_NOT_FOUND", stage=None, status=None)["reason"].startswith("任务关联")
    assert explain_parse_failure(error_code="STALE_TASK", stage=None, status=None)["agent"] == "调度器"
    assert explain_parse_failure(error_code=None, stage=None, status="timed_out")["agent"] == "调度器"
    assert explain_parse_failure(error_code="SUPERSEDED", stage=None, status=None)["stage_label"] == "任务调度"
    assert explain_parse_failure(error_code=None, stage="summarize", status=None)["agent"] == "摘要 Agent"
    assert explain_parse_failure(error_code=None, stage="parse", status=None)["agent"] == "摘要 Agent"
    assert explain_parse_failure(error_code=None, stage="validate", status=None)["agent"] == "校验 Agent"
    assert explain_parse_failure(error_code=None, stage="graph", status=None)["agent"] == "图谱 Agent"
    assert explain_parse_failure(error_code=None, stage="persist", status=None)["agent"] == "持久化"
    assert explain_parse_failure(error_code="WORKER_ERROR", stage="unknown", status=None)["agent"] == "解析流水线"
    assert "UNKNOWN" in explain_parse_failure(error_code=None, stage=None, status=None)["reason"]


def test_admin_overview_tasks_users_and_quality(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'overview.db'}")
    with _session(tmp_path, "overview.db") as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="admin-paper", title="Admin Paper", abstract="abs")],
        ).items[0].paper_id
        user = User(email="user@example.com", password_hash=hash_password("pass"), role="user")
        session.add(user)
        session.commit()
        task, _ = create_task(session, paper_id, "full_parse", "admin-task-key")
        update_task(session, task.task_id, TaskUpdate(status="running", stage="fetch"))
        update_task(session, task.task_id, TaskUpdate(status="failed", error_code="PARSE_FAILED", stage="fetch"))

        overview = admin_overview(session, settings)
        assert overview["metrics"]["papers"] == 1
        assert overview["metrics"]["users"] == 1
        assert overview["task_counts"]["failed"] == 1
        assert any(agent["id"] == "parse" for agent in overview["agents"])

        tasks = admin_tasks(session, limit=5)
        assert tasks[0]["paper_id"] == paper_id
        assert tasks[0]["status"] == "failed"

        users = admin_users(session, limit=10)
        assert users[0]["email"] == "user@example.com"

        quality = admin_quality(session, limit=10)
        assert quality["exceptions"]
        assert quality["exceptions"][0]["paper"] == paper_id
        assert "queue" in quality


def test_update_user_status_and_delete_user(tmp_path) -> None:
    with _session(tmp_path, "users.db") as session:
        admin = User(email="admin@example.com", password_hash=hash_password("pass"), role="admin")
        target = User(email="target@example.com", password_hash=hash_password("pass"), role="user")
        session.add_all([admin, target])
        session.commit()
        session.refresh(target)

        updated = update_user_status(session, target.id, False)
        assert updated["status"] == "禁用"

        try:
            update_user_status(session, admin.id, False)
        except ValueError as exc:
            assert str(exc) == "ADMIN_CANNOT_DISABLE"
        else:
            raise AssertionError("expected ADMIN_CANNOT_DISABLE")

        deleted = delete_user(session, target.id)
        assert deleted["deleted"] is True
        assert deleted["email"] == "target@example.com"

        try:
            delete_user(session, admin.id)
        except ValueError as exc:
            assert str(exc) == "ADMIN_CANNOT_DELETE"
        else:
            raise AssertionError("expected ADMIN_CANNOT_DELETE")

        try:
            update_user_status(session, 9999, True)
        except ValueError as exc:
            assert str(exc) == "USER_NOT_FOUND"
        else:
            raise AssertionError("expected USER_NOT_FOUND")


def test_delete_user_cascades_profile_and_actions(tmp_path) -> None:
    with _session(tmp_path, "delete-cascade.db") as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="del-user-paper", title="Del User Paper")],
        ).items[0].paper_id
        target = User(email="cascade@example.com", password_hash=hash_password("pass"), role="user")
        session.add(target)
        session.commit()
        session.refresh(target)
        uid = str(target.id)
        session.add(UserProfile(user_id=uid, persona="研究", topics=[], preferences={}))
        session.add(
            UserAction(
                user_id=uid,
                paper_id=paper_id,
                action_type="favorite",
                payload_json={"favorite": True},
                occurred_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        deleted = delete_user(session, target.id)
        assert deleted["deleted"] is True
        assert session.get(UserProfile, uid) is None

def test_admin_quality_skips_deleted_papers(tmp_path) -> None:
    with _session(tmp_path, "quality.db") as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="deleted-paper", title="Deleted Paper")],
        ).items[0].paper_id
        task, _ = create_task(session, paper_id, "full_parse", "quality-task")
        update_task(session, task.task_id, TaskUpdate(status="running", stage="fetch"))
        update_task(session, task.task_id, TaskUpdate(status="failed", error_code="PARSE_FAILED", stage="fetch"))
        paper = session.get(Paper, paper_id)
        assert paper is not None
        paper.deleted_at = datetime.now(timezone.utc)
        session.commit()

        quality = admin_quality(session, limit=20)
        assert quality["exceptions"] == []
