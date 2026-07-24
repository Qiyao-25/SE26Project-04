"""Unit tests for same-origin PDF cache/stream helper."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.model import Paper, PaperContent
from app.service.pdf_stream import load_paper_pdf_bytes
from app.service.papers import PaperServiceError


def test_load_paper_pdf_from_storage_path(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 cached")
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}",
        auth_secret="test-secret",
        paper_storage_dir=str(tmp_path / "pdfs"),
    )

    paper = Paper(id=7, arxiv_id="2401.00001", pdf_url="https://arxiv.org/pdf/2401.00001.pdf", deleted_at=None)
    content = PaperContent(paper_id=7, storage_path=str(pdf_path), mime_type="application/pdf")

    session = MagicMock()
    session.get.side_effect = lambda model, key: paper if model is Paper else content

    data, ctype = load_paper_pdf_bytes(session, 7, settings=settings)
    assert data.startswith(b"%PDF")
    assert ctype == "application/pdf"


def test_load_paper_pdf_missing_paper(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}",
        auth_secret="test-secret",
        paper_storage_dir=str(tmp_path / "pdfs"),
    )
    session = MagicMock()
    session.get.return_value = None
    with pytest.raises(PaperServiceError) as exc:
        load_paper_pdf_bytes(session, 99, settings=settings)
    assert exc.value.code == "PAPER_NOT_FOUND"
