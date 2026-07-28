"""Benchmark PaperMate's required Web API scenarios on isolated test data.

The benchmark creates a temporary SQLite database with 100 papers, starts a
local OpenAI-compatible stub, then starts Uvicorn.  The QA scenario therefore
measures the application's authentication, retrieval and response-assembly
cost without network-model latency.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

PERFORMANCE_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = PERFORMANCE_DIR.parent
BACKEND_DIR = REPOSITORY_DIR / "TechPrototype" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, Paper, StructuredResult, TextChunk


REQUIRED_CONCURRENCY = 100
REQUIRED_PAPERS = 100
RESPONSE_LIMIT_MS = 3_000.0


class _LlmStubHandler(BaseHTTPRequestHandler):
    """Return deterministic, contract-valid QA responses with no model delay."""

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(content_length) or b"{}")
        messages = payload.get("messages") or []
        system = str(messages[0].get("content", "")) if messages else ""
        if "论文问答检索规划 Agent" in system:
            content = {"paper_related": True, "search_queries": ["self-attention", "benchmark"]}
        else:
            content = {
                "answer": "论文使用 self-attention 建模序列依赖，并在基准任务上评估。",
                "evidence_ids": ["E1"],
                "refuse": False,
            }
        body = json.dumps({"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return



class _LlmStubServer(ThreadingHTTPServer):
    request_queue_size = 256
    daemon_threads = True


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _seed_database(database_url: str) -> None:
    engine = create_engine_for(Settings(environment="test", database_url=database_url))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        papers = [
            Paper(
                arxiv_id=f"perf.{index:05d}",
                title=f"Performance Benchmark Paper {index}: Self-Attention Retrieval",
                abstract="This benchmark paper studies self-attention retrieval and evaluation.",
                published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                primary_category="cs.CL",
                ingest_status="qa_ready" if index == 1 else "metadata_only",
                chunk_count=2 if index == 1 else 0,
            )
            for index in range(1, REQUIRED_PAPERS + 1)
        ]
        session.add_all(papers)
        session.flush()
        session.add_all(
            [
                TextChunk(
                    paper_id=papers[0].id,
                    chunk_id="perf-c1",
                    page_no=1,
                    section="method",
                    content="The self-attention architecture models dependencies across sequence positions.",
                ),
                TextChunk(
                    paper_id=papers[0].id,
                    chunk_id="perf-c2",
                    page_no=2,
                    section="experiments",
                    content="Benchmark evaluation measures performance on translation tasks.",
                ),
                StructuredResult(
                    paper_id=papers[0].id,
                    result_type="summary",
                    version=1,
                    content_json={"summary": "Self-attention retrieval benchmark."},
                    source_locator={"source": "performance-fixture"},
                ),
            ]
        )
        session.commit()


def _wait_ready(base_url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 15
    with httpx.Client(base_url=base_url, timeout=1) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Uvicorn exited before becoming ready")
            try:
                if client.get("/health").status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
    raise RuntimeError("Uvicorn did not become ready within 15 seconds")


def _summarize(name: str, results: list[tuple[float, int]]) -> dict[str, Any]:
    latencies = sorted(value for value, _status in results)
    statuses = [status for _value, status in results]

    def percentile(value: float) -> float:
        return latencies[max(0, min(len(latencies) - 1, int(len(latencies) * value + 0.999999) - 1))]

    successes = sum(200 <= status < 300 for status in statuses)
    maximum = max(latencies)
    return {
        "scenario": name,
        "requests": len(results),
        "successes": successes,
        "errors": len(results) - successes,
        "p50_ms": round(percentile(0.50), 2),
        "p95_ms": round(percentile(0.95), 2),
        "p99_ms": round(percentile(0.99), 2),
        "max_ms": round(maximum, 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "passes_requirement": successes == len(results) and maximum < RESPONSE_LIMIT_MS,
    }


def _run_scenario(base_url: str, *, name: str, method: str, path: str, headers: dict[str, str], payload: dict[str, Any] | None, concurrency: int) -> dict[str, Any]:
    # Use a fresh pool for each scenario, so a saturated prior route cannot
    # affect the next measurement through stale client connections.
    limits = httpx.Limits(max_connections=concurrency + 10, max_keepalive_connections=concurrency)
    with httpx.Client(base_url=base_url, timeout=4, limits=limits) as client:
        # Warm up route compilation, authentication and SQLite connection creation.
        for _ in range(5):
            try:
                client.request(method, path, headers=headers, json=payload).raise_for_status()
            except httpx.HTTPError as exc:
                raise RuntimeError(f"{name} 预热失败: {exc}") from exc

        def one() -> tuple[float, int]:
            started = time.perf_counter()
            try:
                response = client.request(method, path, headers=headers, json=payload)
                return (time.perf_counter() - started) * 1_000, response.status_code
            except httpx.HTTPError:
                return (time.perf_counter() - started) * 1_000, 0

        started = time.perf_counter()
        results: list[tuple[float, int]] = []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(one) for _ in range(concurrency)]
            for future in as_completed(futures):
                results.append(future.result())
    summary = _summarize(name, results)
    elapsed = time.perf_counter() - started
    summary["throughput_rps"] = round(concurrency / elapsed, 2) if elapsed else 0
    return summary


def _stop_server(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def run(concurrency: int, workers: int) -> dict[str, Any]:
    if concurrency != REQUIRED_CONCURRENCY:
        raise ValueError(f"验收测试必须使用 {REQUIRED_CONCURRENCY} 并发")
    if workers < 1:
        raise ValueError("worker 数量必须大于 0")
    with tempfile.TemporaryDirectory(prefix="papermate-performance-") as temp_dir:
        database_path = Path(temp_dir) / "performance.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        _seed_database(database_url)
        llm_port = _free_port()
        llm_server = _LlmStubServer(("127.0.0.1", llm_port), _LlmStubHandler)
        llm_thread = threading.Thread(target=llm_server.serve_forever, daemon=True)
        llm_thread.start()
        environment = os.environ.copy()
        environment.update(
            {
                "PAPERMATE_ENV": "performance",
                "PAPERMATE_DATABASE_URL": database_url,
                "PAPERMATE_DB_POOL_SIZE": "30",
                "PAPERMATE_DB_MAX_OVERFLOW": "20",
                "PAPERMATE_DB_POOL_TIMEOUT_S": "3",
                "PAPERMATE_AUTH_CACHE_TTL_S": "60",
                "PAPERMATE_AUTH_SECRET": "performance-test-secret",
                "PAPERMATE_CRAWL_ENABLED": "false",
                "PAPERMATE_PARSE_SCHEDULER_ENABLED": "false",
                "PAPERMATE_LLM_API_KEY": "performance-stub-key",
                "PAPERMATE_LLM_MODEL": "performance-stub",
                "PAPERMATE_LLM_API_BASE": f"http://127.0.0.1:{llm_port}/v1",
            }
        )
        scenario_specs = [
            ("检索：论文列表", "GET", "/api/papers?keyword=self-attention&page=1&page_size=20", {}, None),
            ("学习管理：读取行为", "GET", "/api/learning/actions?user_id={user_id}", {"needs_auth": "true"}, None),
            ("问答：本地 LLM stub", "POST", "/api/papers/1/qa", {"needs_auth": "true"}, {"question": "论文使用什么架构？", "scope": "both"}),
        ]
        scenarios = []
        try:
            for index, (name, method, path_template, header_spec, payload) in enumerate(scenario_specs, start=1):
                api_port = _free_port()
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--workers",
                        str(workers),
                        "--no-access-log",
                    ],
                    cwd=BACKEND_DIR,
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                base_url = f"http://127.0.0.1:{api_port}"
                try:
                    _wait_ready(base_url, process)
                    with httpx.Client(base_url=base_url, timeout=10) as client:
                        registered = client.post(
                            "/api/auth/register",
                            json={"email": f"performance-{index}@example.com", "password": "password123"},
                        )
                        registered.raise_for_status()
                        auth = registered.json()["data"]
                    headers = {"Authorization": f"Bearer {auth['access_token']}"} if header_spec.get("needs_auth") else {}
                    scenarios.append(
                        _run_scenario(
                            base_url,
                            name=name,
                            method=method,
                            path=path_template.format(user_id=auth["user"]["user_id"]),
                            headers=headers,
                            payload=payload,
                            concurrency=concurrency,
                        )
                    )
                finally:
                    _stop_server(process)
            return {
                "sample_papers": REQUIRED_PAPERS,
                "concurrency": concurrency,
                "workers": workers,
                "database": "SQLite temporary fixture; PostgreSQL is required for production validation",
                "response_limit_ms": RESPONSE_LIMIT_MS,
                "qa_llm": "local deterministic HTTP stub; external LLM latency excluded",
                "scenarios": scenarios,
                "passed": all(item["passes_requirement"] for item in scenarios),
            }
        finally:
            llm_server.shutdown()
            llm_server.server_close()
            llm_thread.join(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the required 100-concurrent Web API performance benchmark")
    parser.add_argument("--concurrency", type=int, default=REQUIRED_CONCURRENCY)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=PERFORMANCE_DIR / "reports" / "performance-web.json")
    args = parser.parse_args()
    report = run(args.concurrency, args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
