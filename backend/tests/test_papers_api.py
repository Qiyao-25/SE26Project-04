from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def create_client() -> TestClient:
    settings = Settings(environment="test", database_url="sqlite:///:memory:")
    return TestClient(create_app(settings))


def test_search_and_detail_flow() -> None:
    client = create_client()
    search = client.post("/api/papers/search", json={"query": "Transformer", "page": 1, "pageSize": 12})
    assert search.status_code == 200
    payload = search.json()["data"]
    assert payload["total"] >= 2
    assert any(item["paperId"] == "attention" for item in payload["items"])

    detail = client.get("/api/papers/attention")
    assert detail.status_code == 200
    assert detail.json()["data"]["arxivId"] == "1706.03762"


def test_content_summary_and_qa_flow() -> None:
    client = create_client()
    assert client.get("/api/papers/attention/content").status_code == 200
    assert client.get("/api/papers/attention/summary").status_code == 200

    qa = client.post(
        "/api/papers/attention/qa",
        json={"conversationId": None, "question": "这篇论文的方法是什么？", "history": []},
    )
    assert qa.status_code == 200
    assert qa.json()["data"]["citations"]


def test_not_found() -> None:
    client = create_client()
    response = client.get("/api/papers/not-found")
    assert response.status_code == 404
