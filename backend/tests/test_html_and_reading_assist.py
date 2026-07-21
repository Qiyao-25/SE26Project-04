"""Unit tests for HTML extract + reading-mode assist wiring."""

from sqlalchemy.orm import Session

from app.agents.reading_mode_agent import ReadingAssistResult
from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import PaperUpsert
from app.service.parse_agent_runner import _Ar5ivHtmlParser, _text_to_chunks
from app.service.papers import batch_upsert_papers, get_reading_assist


def test_html_parser_extracts_sections():
    html = """
    <html><body>
      <h2>1. Introduction</h2>
      <p>This paragraph explains the motivation of the paper with enough characters to pass the length filter for extraction.</p>
      <h2>2. Method</h2>
      <p>We propose a simple architecture that combines attention and feed-forward layers for sequence modeling tasks.</p>
    </body></html>
    """
    parser = _Ar5ivHtmlParser()
    parser.feed(html)
    parser.close()
    assert len(parser.paragraphs) >= 2
    sections = {section for section, _ in parser.paragraphs}
    assert any("introduction" in s.casefold() or "method" in s.casefold() for s in sections)


def test_text_to_chunks_keeps_html_section_markers():
    text = (
        "[section: introduction] This is a long enough introduction paragraph about the problem and motivation of the work. "
        "It continues with more context so chunking can keep the section label. "
        "[section: method] We describe the architecture and training objective with sufficient detail for a chunk."
    )
    chunks = _text_to_chunks(text, max_chunks=10)
    assert chunks
    assert any(c["section"] == "introduction" for c in chunks)
    assert any(c["section"] == "method" for c in chunks)


def test_get_reading_assist_uses_reading_mode_agent(tmp_path, monkeypatch):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'assist.db'}",
        assist_agent_enabled=True,
        llm_api_key="fake-key",
        llm_model="demo",
    )
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)

    def fake_run(self, **kwargs):
        return ReadingAssistResult(
            mode=kwargs.get("mode") or "研究",
            headline="Agent 生成的研究导读",
            sections=[{"title": "核心贡献", "bullets": ["来自 ReadingModeAgent"]}],
            takeaways=["要点A", "要点B", "要点C"],
            next_steps=["继续精读"],
            source="llm_reading_mode_agent",
        )

    monkeypatch.setattr("app.agents.reading_mode_agent.ReadingModeAgent.run", fake_run)

    with Session(engine) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="assist-1", title="Assist Paper", abstract="An abstract about assist.")],
        ).items[0].paper_id
        data = get_reading_assist(session, paper_id, mode="研究", force=True, settings=settings)

    assert data.source == "llm_reading_mode_agent"
    assert data.generated is True
    assert data.headline.startswith("Agent")
    assert data.sections[0].bullets[0] == "来自 ReadingModeAgent"


def test_get_reading_assist_falls_back_without_llm(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'assist2.db'}",
        assist_agent_enabled=False,
        llm_api_key="",
        agent_api_key=None,
        deepseek_api_key="",
    )
    settings.assist_agent_enabled = False
    settings.llm_api_key = ""
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper_id = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="assist-2", title="Fallback Assist", abstract="Abstract text.")],
        ).items[0].paper_id
        data = get_reading_assist(session, paper_id, mode="新手", force=True, settings=settings)
    assert data.source == "heuristic"
    assert data.mode == "新手"
    assert data.sections
