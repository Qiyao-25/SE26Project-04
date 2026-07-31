import json
import urllib.request
import urllib.error


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
        raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc


result = req(
    "POST",
    "/api/papers/smart-search",
    {"query": "有哪些关于注意力机制或Transformer的论文？", "page": 1, "page_size": 6},
)["data"]
print("total", result.get("total"))
print("keywords", result.get("keywords"))
print("rewritten", result.get("rewritten_query"))
print("plan_source", result.get("plan_source"), "answer_source", result.get("answer_source"))
print("answer", (result.get("answer") or "")[:280])
print("titles", [item.get("title") for item in (result.get("items") or [])[:3]])
print("RESULT", "PASS" if result.get("answer") is not None else "FAIL")
