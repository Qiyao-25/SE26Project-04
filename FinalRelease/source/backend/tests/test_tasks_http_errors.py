"""HTTP error coverage for task routes."""

from app.schema.papers import TaskUpdate
from app.service.tasks import create_task, update_task
from tests.conftest import seed_paper


def test_task_http_not_found_and_forbidden(client, user_headers, admin_headers, db_session) -> None:
    missing = client.get("/api/tasks/99999", headers=user_headers)
    assert missing.status_code == 404

    paper_id = seed_paper(db_session, arxiv_id="task-owner", title="Task Owner")
    task, _ = create_task(db_session, paper_id, "full_parse", "owner-task", owner_user_id=1)
    other = register_other(client)
    forbidden = client.get(f"/api/tasks/{task.task_id}", headers=other)
    assert forbidden.status_code == 403

    delete_ok = client.delete(f"/api/tasks/{task.task_id}", headers=admin_headers)
    assert delete_ok.status_code == 200


def test_task_delete_and_retry_conflicts(client, admin_headers, db_session) -> None:
    running_paper = seed_paper(db_session, arxiv_id="task-conflict-run", title="Task Conflict Run")
    running_task, _ = create_task(db_session, running_paper, "full_parse", "conflict-task-running")
    update_task(db_session, running_task.task_id, TaskUpdate(status="running", stage="parse"))

    delete_resp = client.delete(f"/api/tasks/{running_task.task_id}", headers=admin_headers)
    assert delete_resp.status_code == 409
    assert delete_resp.json()["code"] == "TASK_DELETE_CONFLICT"

    queued_paper = seed_paper(db_session, arxiv_id="task-conflict-queue", title="Task Conflict Queue")
    queued_task, _ = create_task(db_session, queued_paper, "full_parse", "conflict-task-queued")
    retry_resp = client.post(f"/api/tasks/{queued_task.task_id}/retry", headers=admin_headers)
    assert retry_resp.status_code == 409
    assert retry_resp.json()["code"] == "TASK_RETRY_CONFLICT"


def register_other(client):
    from tests.conftest import auth_header, register_user

    return auth_header(register_user(client, email="other-task@example.com")["access_token"])
