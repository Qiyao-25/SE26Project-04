"""Unit tests for PDF cache helpers."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.model import Paper, PaperContent
from app.service.pdf_stream import ensure_paper_pdf_cached, load_paper_pdf_bytes, pdf_cache_stats
from app.service.papers import PaperServiceError


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}",
        auth_secret="test-secret",
        paper_storage_dir=str(tmp_path / "pdfs"),
    )


def test_load_paper_pdf_from_storage_path(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 cached")
    settings = _settings(tmp_path)

    paper = Paper(id=7, arxiv_id="2401.00001", pdf_url="https://arxiv.org/pdf/2401.00001.pdf", deleted_at=None)
    content = PaperContent(paper_id=7, storage_path=str(pdf_path), mime_type="application/pdf", checksum="x")

    session = MagicMock()
    session.get.side_effect = lambda model, key: paper if model is Paper else content

    data, ctype = load_paper_pdf_bytes(session, 7, settings=settings)
    assert data.startswith(b"%PDF")
    assert ctype == "application/pdf"


def test_ensure_missing_paper(tmp_path):
    settings = _settings(tmp_path)
    session = MagicMock()
    session.get.return_value = None
    with pytest.raises(PaperServiceError) as exc:
        ensure_paper_pdf_cached(session, 99, settings=settings)
    assert exc.value.code == "PAPER_NOT_FOUND"


def test_pdf_cache_stats_empty(tmp_path):
    settings = _settings(tmp_path)
    session = MagicMock()
    session.scalar.side_effect = [0, 0]
    stats = pdf_cache_stats(session, settings)
    assert stats["papers"] == 0
    assert stats["disk_pdf_files"] == 0
    assert "pdfs" in stats["storage_dir"].replace("\\", "/")
