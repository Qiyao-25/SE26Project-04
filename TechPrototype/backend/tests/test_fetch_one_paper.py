"""Tests for single-paper arXiv fetch (id / title)."""

from unittest.mock import MagicMock

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.service.arxiv_client import ArxivClient, ArxivPaperMeta
from app.service.papers import PaperServiceError, fetch_one_paper
from sqlalchemy.orm import Session

SAMPLE_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <title>Attention Is All You Need For Tests</title>
    <summary>Abstract text.</summary>
    <published>2024-01-01T00:00:00Z</published>
    <author><name>Alice Example</name></author>
    <link href="https://arxiv.org/abs/2401.01234" rel="alternate" type="text/html"/>
    <link title="pdf" href="https://arxiv.org/pdf/2401.01234" rel="related" type="application/pdf"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.CL"/>
    <category term="cs.CL"/>
  </entry>
</feed>
"""


def test_resolve_query_prefers_arxiv_id(monkeypatch):
    client = ArxivClient()
    calls: list[str] = []

    def fake_get(url: str) -> bytes:
        calls.append(url)
        return SAMPLE_ATOM

    monkeypatch.setattr(client, "_http_get", fake_get)
    hits = client.resolve_query("https://arxiv.org/abs/2401.01234")
    assert len(hits) == 1
    assert hits[0].arxiv_id == "2401.01234"
    assert "id_list=2401.01234" in calls[0]


def test_resolve_query_title_uses_ti_search(monkeypatch):
    client = ArxivClient()

    def fake_get(url: str) -> bytes:
        assert "search_query=" in url
        return SAMPLE_ATOM

    monkeypatch.setattr(client, "_http_get", fake_get)
    hits = client.resolve_query("Attention Is All You Need For Tests")
    assert len(hits) == 1
    assert "Attention" in hits[0].title


def test_fetch_one_paper_upserts(monkeypatch):
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)

    meta = ArxivPaperMeta(
        arxiv_id="2401.01234",
        title="Attention Is All You Need For Tests",
        authors=["Alice Example"],
        abstract="Abstract text.",
        categories=["cs.CL"],
        pdf_url="https://arxiv.org/pdf/2401.01234",
        abs_url="https://arxiv.org/abs/2401.01234",
        published="2024-01-01T00:00:00Z",
    )

    fake_client = MagicMock()
    fake_client.resolve_query.return_value = [meta]
    monkeypatch.setattr("app.service.arxiv_client.ArxivClient", lambda **kwargs: fake_client)

    with Session(engine) as session:
        result = fetch_one_paper(session, query="2401.01234", parse=False)
        assert result.created is True
        assert result.matched_by == "arxiv_id"
        assert result.item.arxiv_id == "2401.01234"
        assert result.task_id is None

        again = fetch_one_paper(session, query="2401.01234", parse=False)
        assert again.created is False
        assert again.item.paper_id == result.item.paper_id


def test_fetch_one_paper_not_found(monkeypatch):
    engine = create_engine_for(Settings(environment="test", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)

    fake_client = MagicMock()
    fake_client.resolve_query.return_value = []
    monkeypatch.setattr("app.service.arxiv_client.ArxivClient", lambda **kwargs: fake_client)

    with Session(engine) as session:
        try:
            fetch_one_paper(session, query="nonexistent-title-xyz", parse=False)
            assert False, "expected PaperServiceError"
        except PaperServiceError as exc:
            assert exc.code == "PAPER_NOT_FOUND"
