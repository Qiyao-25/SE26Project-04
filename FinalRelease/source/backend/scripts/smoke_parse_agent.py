import json
import time
import urllib.request


def req(method, path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:8000" + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode())


papers = [
    {
        "arxiv_id": "1706.03762",
        "title": "Attention Is All You Need",
        "authors": [{"name": "Ashish Vaswani"}],
        "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer.",
        "primary_category": "cs.CL",
        "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
        "source_url": "https://arxiv.org/abs/1706.03762",
        "ingest_status": "metadata_only",
    }
]
batch = req("POST", "/api/papers/batch", papers)
paper_id = batch["data"]["items"][0]["paper_id"]
print("paper_id", paper_id)

task = req(
    "POST",
    f"/api/papers/{paper_id}/parse",
    {"task_type": "full_parse", "force": True},
    {"Idempotency-Key": f"test-agent-{int(time.time())}"},
)
print("task", task["data"])
tid = task["data"]["task_id"]
status = task["data"]["status"]

for i in range(60):
    time.sleep(3)
    st = req("GET", f"/api/tasks/{tid}")
    status = st["data"]["status"]
    stage = st["data"].get("stage")
    err = st["data"].get("error_code")
    print(f"poll {i}: status={status} stage={stage} err={err}")
    if status in ("succeeded", "failed", "timed_out"):
        break

wiki = req("GET", f"/api/papers/{paper_id}/summary")
d = wiki["data"]
print("parseStatus", d.get("parseStatus"))
print("summary_preview", (d.get("summary") or "")[:240])
print("concepts", len(d.get("concepts") or []))
print("methods", len(d.get("methods") or []))
print("experiments", len(d.get("experiments") or []))
print("flags", d.get("validationFlags"))
print("RESULT", "PASS" if status == "succeeded" and d.get("summary") else "FAIL")
