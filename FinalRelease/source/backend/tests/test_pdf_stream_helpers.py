"""Unit tests for PDF stream helper functions."""

from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, Paper, PaperContent
from app.schema.papers import PaperUpsert
from app.service.papers import batch_upsert_papers
from app.service.pdf_stream import (
    _persist_cache,
    _resolve_pdf_url,
    local_pdf_path,
    normalize_arxiv_id,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'pdf.db').as_posix()}",
        paper_storage_dir=str(tmp_path / "pdfs"),
    )


def test_normalize_arxiv_id_variants() -> None:
    assert normalize_arxiv_id("arXiv:1706.03762") == "1706.03762"
    assert normalize_arxiv_id("oai:arXiv.org:2401.00001") == "2401.00001"
    assert normalize_arxiv_id("2401.00001.pdf") == "2401.00001"
    assert normalize_arxiv_id("") is None


def test_resolve_pdf_url_from_arxiv_id() -> None:
    paper = Paper(id=1, arxiv_id="1706.03762", pdf_url=None)
    assert _resolve_pdf_url(paper) == "https://arxiv.org/pdf/1706.03762.pdf"
    paper_bad = Paper(id=2, arxiv_id=None, pdf_url="https://arxiv.org/pdf/9999.99999.pdf")
    assert _resolve_pdf_url(paper_bad) == "https://arxiv.org/pdf/9999.99999.pdf"
    paper_oai = Paper(id=3, arxiv_id="2401.00002", pdf_url="oai:arXiv.org:2401.00002")
    assert _resolve_pdf_url(paper_oai) == "https://arxiv.org/pdf/2401.00002.pdf"
    paper_only_url = Paper(id=4, arxiv_id=None, pdf_url="https://arxiv.org/pdf/8888.88888.pdf")
    assert _resolve_pdf_url(paper_only_url) == "https://arxiv.org/pdf/8888.88888.pdf"


def test_resolve_storage_dir_relative(tmp_path) -> None:
    from app.service.pdf_stream import resolve_storage_dir

    settings = Settings(environment="test", database_url="sqlite:///:memory:", paper_storage_dir="relative/pdfs")
    path = resolve_storage_dir(settings)
    assert path.is_dir()


def test_persist_cache_and_load_from_local_cache(tmp_path) -> None:
    settings = _settings(tmp_path)
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    pdf_bytes = b"%PDF-1.4 cached-content"

    with Session(engine) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="2401.00001", title="Cached Paper", pdf_url="https://arxiv.org/pdf/2401.00001.pdf")],
        ).items[0].paper_id
        paper = session.get(Paper, paper_id)
        assert paper is not None
        cache_path = tmp_path / "pdfs" / "2401.00001.pdf"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(pdf_bytes)
        _persist_cache(session, paper, cache_path, pdf_bytes)
        loaded = session.get(PaperContent, paper_id)
        assert loaded is not None
        assert loaded.storage_path == str(cache_path)
        assert local_pdf_path(session, paper, settings) == cache_path
