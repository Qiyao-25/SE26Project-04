"""Tests for parse agent text extraction helpers."""

from io import BytesIO
from pathlib import Path

import pytest

from app.core.config import Settings
from app.model import Paper
from app.service import parse_agent_runner
from app.service.parse_agent_runner import _download_and_extract_html, _download_and_extract_pdf, _extract_paper_text


def _paper(**kwargs) -> Paper:
    defaults = {"id": 1, "arxiv_id": "2401.00001", "title": "Sample", "abstract": "Abstract fallback text."}
    defaults.update(kwargs)
    return Paper(**defaults)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'extract.db').as_posix()}",
        paper_storage_dir=str(tmp_path / "pdfs"),
        parse_agent_max_pages=3,
    )


def test_extract_paper_text_pdf_path(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        parse_agent_runner,
        "_download_and_extract_pdf",
        lambda url, arxiv_id, storage_dir, max_pages: ("[page 1] extracted pdf text long enough", 1, str(tmp_path / "x.pdf")),
    )
    text, pages, source, path = _extract_paper_text(_paper(), settings)
    assert source == "pdf"
    assert "extracted pdf text" in text
    assert pages == 1
    assert path


def test_extract_paper_text_html_path(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        parse_agent_runner,
        "_download_and_extract_pdf",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("pdf failed")),
    )
    monkeypatch.setattr(
        parse_agent_runner,
        "_download_and_extract_html",
        lambda url, max_chars=120_000: "[section: intro] html paragraph long enough for extraction",
    )
    text, pages, source, path = _extract_paper_text(_paper(), settings)
    assert source == "ar5iv_html"
    assert "html paragraph" in text
    assert pages == 1
    assert path is None


def test_extract_paper_text_abstract_fallback(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(parse_agent_runner, "_download_and_extract_pdf", lambda *args, **kwargs: ("", 0, str(tmp_path / "empty.pdf")))
    monkeypatch.setattr(parse_agent_runner, "_download_and_extract_html", lambda *args, **kwargs: "")
    text, pages, source, path = _extract_paper_text(_paper(abstract="Only abstract remains."), settings)
    assert source == "abstract_fallback"
    assert text == "Only abstract remains."
    assert pages == 0
    assert path is None


def test_download_and_extract_html_from_bytes(monkeypatch) -> None:
    html = b"""<!doctype html><html><body>
    <h2>Introduction</h2><p>This is a long enough paragraph for the html extractor to keep in output.</p>
    </body></html>"""

    class FakeResponse:
        def read(self):
            return html

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
    text, count = _download_and_extract_html("https://example.com/paper.html")
    assert count >= 1
    assert "Introduction" in text or "paragraph" in text


def test_download_and_extract_pdf_with_pypdf(tmp_path, monkeypatch) -> None:
    pytest.importorskip("pypdf")
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    pdf_bytes = buffer.getvalue()

    class FakeResponse:
        def read(self):
            return pdf_bytes

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
    text, pages, storage_path = _download_and_extract_pdf(
        "https://arxiv.org/pdf/2401.00001.pdf",
        arxiv_id="2401.00001",
        storage_dir=tmp_path / "pdfs",
        max_pages=1,
    )
    assert pages == 1
    assert Path(storage_path).exists()
    assert isinstance(text, str)


def test_download_and_extract_html_tuple_parser(monkeypatch) -> None:
    html = b"""<!doctype html><html><body>
    <section><h2>Methods</h2><p>This methods section has enough characters to pass the parser threshold easily.</p></section>
    </body></html>"""

    class FakeResponse:
        def read(self):
            return html

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
    from app.service import parse_agent_runner

    text, count = parse_agent_runner._download_and_extract_html("https://ar5iv.org/html/2401.00001", max_chars=5000)
    assert count >= 1
    assert "Methods" in text or "methods" in text.lower()
