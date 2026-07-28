"""HTTP and parsing helpers for arXiv client."""

import urllib.error

import pytest

from app.service.arxiv_client import ArxivClient, _parse_atom_feed


SAMPLE_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <title>Example Atom Paper</title>
    <summary>Abstract text.</summary>
    <published>2024-01-01T00:00:00Z</published>
    <author><name>Alice</name></author>
    <category term="cs.CL"/>
  </entry>
</feed>
"""


def test_parse_atom_feed_extracts_pdf_url() -> None:
    papers = _parse_atom_feed(SAMPLE_ATOM)
    assert len(papers) == 1
    assert papers[0].arxiv_id == "2401.01234"
    assert papers[0].pdf_url == "https://arxiv.org/pdf/2401.01234.pdf"
    assert papers[0].authors == ["Alice"]


def test_http_get_retries_on_429(monkeypatch) -> None:
    client = ArxivClient(min_interval_s=0, max_retries=3, rate_limit_wait_s=0)
    calls = {"count": 0}

    def fake_urlopen(req, timeout=60):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", hdrs=None, fp=None)
        return type("Resp", (), {"read": lambda self: SAMPLE_ATOM, "__enter__": lambda self: self, "__exit__": lambda *a: False})()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
    papers = client.search(search_query="cat:cs.CL", max_results=1)
    assert papers[0].arxiv_id == "2401.01234"
    assert calls["count"] == 2


def test_fetch_helpers_return_empty(monkeypatch) -> None:
    client = ArxivClient(min_interval_s=0)
    assert client.fetch_category_rss("") == []
    assert client.fetch_by_id("") is None
    assert client.fetch_by_title("") == []
    assert client.resolve_query("") == []

    def boom(url):
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "_http_get", boom)
    with pytest.raises(RuntimeError):
        client.search(search_query="cat:cs.CL")
