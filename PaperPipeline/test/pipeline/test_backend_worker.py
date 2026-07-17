from pathlib import Path

from pipeline.worker.backend_worker import BackendParseWorker


class FakeBackendClient:
    def __init__(self, html_dir: Path) -> None:
        self.html_dir = html_dir
        self.stages: list[tuple[int, str, str | None]] = []
        self.saved_chunks = []
        self.saved_results = []

    def update_task(self, task_id: int, status: str, error_code: str | None = None, stage: str | None = None):
        self.stages.append((task_id, status, stage))
        return {"task_id": task_id, "status": status, "stage": stage}

    def get_paper(self, paper_id: int):
        return {"paper_id": paper_id, "arxiv_id": "demo-html", "title": "HTML Demo", "abstract": "Attention model evaluation abstract."}

    def save_chunks(self, paper_id: int, chunks):
        self.saved_chunks.extend(chunks)
        return {"upserted": len(chunks)}

    def save_structured_results(self, task_id: int, results):
        self.saved_results.extend(results)
        return {"task_id": task_id, "status": "succeeded"}


def test_backend_worker_persists_html_pipeline_result(tmp_path: Path) -> None:
    html_dir = tmp_path / "html"
    html_dir.mkdir()
    (html_dir / "demo-html.html").write_text(
        "<html><body><h2>1 Introduction</h2>"
        "<p>The attention model improves representation quality for this evaluation sample.</p>"
        "<h2>3 Experiments</h2>"
        "<p>We evaluate the approach on a benchmark and report accuracy improvements.</p>"
        "</body></html>",
        encoding="utf-8",
    )
    client = FakeBackendClient(html_dir)
    worker = BackendParseWorker(client, tmp_path / "pdf", html_dir=html_dir, prefer_html=True, min_chars=80)

    result = worker.process_task({"task_id": 7, "paper_id": 3})

    assert result["status"] == "succeeded"
    assert result["source_type"] == "html"
    assert result["chunks"] == 2
    assert {stage for _, _, stage in client.stages} >= {"fetch", "parse", "summarize", "validate", "persist"}
    assert {row["result_type"] for row in client.saved_results} >= {"summary", "concepts", "methods", "experiments", "validation"}
