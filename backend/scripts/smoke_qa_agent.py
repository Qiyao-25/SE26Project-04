import json
import urllib.request


def req(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:8000" + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


paper = req("GET", "/api/papers/1")["data"]
print("paper", paper["paper_id"], paper["ingest_status"], paper["chunk_count"], paper["qa_ready"])

result = req(
    "POST",
    "/api/papers/1/qa",
    {
        "question": "这篇论文的核心创新是什么？",
        "history": [],
        "conversationId": None,
    },
)["data"]
print("answer", (result.get("answer") or "")[:300])
print("citations", len(result.get("citations") or []))
if result.get("citations"):
    c0 = result["citations"][0]
    print("cite0", c0.get("sectionTitle"), c0.get("pageNumber"), (c0.get("quote") or "")[:120])
print("RESULT", "PASS" if result.get("answer") and result.get("citations") else "FAIL")
