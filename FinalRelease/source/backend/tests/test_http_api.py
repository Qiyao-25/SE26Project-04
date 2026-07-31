import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.model import Base
from app.schema.papers import PaperUpsert
from app.service.papers import batch_upsert_papers
from app.service.tasks import create_task


pytestmark = pytest.mark.skipif(
    os.environ.get("PAPERMATE_RUN_HTTP_TESTS") != "1",
    reason="real HTTP tests require a local listening socket; set PAPERMATE_RUN_HTTP_TESTS=1",
)


def _free_port() -> int:
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except PermissionError:
        pytest.skip("environment does not permit local listening sockets")


def _prepare_database(database_path: Path, env: dict[str, str]) -> None:
    setup = (
        "from app.core.config import Settings; "
        "from app.core.database import create_engine_for; "
        "from app.model import Base; "
        "Base.metadata.create_all(create_engine_for(Settings()))"
    )
    subprocess.run([sys.executable, "-c", setup], cwd=Path(__file__).resolve().parents[1], env=env, check=True)


def _start_server(database_path: Path):
    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(
        {
            "PAPERMATE_ENV": "test",
            "PAPERMATE_DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            "PAPERMATE_AUTH_SECRET": "test-secret",
            "PAPERMATE_ENABLE_DOCS": "true",
            "PAPERMATE_CRAWL_ENABLED": "false",
            "PAPERMATE_PARSE_SCHEDULER_ENABLED": "false",
        }
    )
    _prepare_database(database_path, env)
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=backend_dir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    client = httpx.Client(base_url=base_url, timeout=3)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if client.get("/health").status_code == 200:
                return process, client, env
        except httpx.HTTPError:
            time.sleep(0.1)
    client.close()
    process.terminate()
    process.wait(timeout=5)
    raise RuntimeError("Uvicorn did not become ready for HTTP integration test")


def test_http_auth_admin_isolation_task_ownership_and_contracts(tmp_path: Path) -> None:
    process, client, env = _start_server(tmp_path / "http.db")
    try:
        registered = client.post(
            "/api/auth/register",
            json={"email": "http-reader-a@example.com", "password": "password123"},
        )
        assert registered.status_code == 200
        token_a = registered.json()["data"]["access_token"]
        user_a = int(registered.json()["data"]["user"]["user_id"])

        registered_b = client.post(
            "/api/auth/register",
            json={"email": "http-reader-b@example.com", "password": "password123"},
        )
        token_b = registered_b.json()["data"]["access_token"]

        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token_a}"}).status_code == 403
        assert client.post("/api/search/chunks", json={"query": "attention"}).status_code == 401

        with Session(create_engine(env["PAPERMATE_DATABASE_URL"])) as session:
            paper_id = batch_upsert_papers(
                session,
                [PaperUpsert(arxiv_id="http-contract-paper", title="HTTP Contract Paper")],
            ).items[0].paper_id
            task, _ = create_task(
                session,
                paper_id,
                "full_parse",
                "http-contract-task",
                owner_user_id=user_a,
            )

        own = client.get(f"/api/tasks/{task.task_id}", headers={"Authorization": f"Bearer {token_a}"})
        other = client.get(f"/api/tasks/{task.task_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert own.status_code == 200
        assert own.json()["data"]["owner_user_id"] == user_a
        assert other.status_code == 403

        detail = client.get(f"/api/papers/{paper_id}")
        assert detail.status_code == 200
        assert detail.json()["data"]["paper_id"] == paper_id

        schema = client.get("/openapi.json").json()["paths"]["/api/papers/{paper_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert "ApiResponse_PaperItem_" in schema["$ref"]
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)
