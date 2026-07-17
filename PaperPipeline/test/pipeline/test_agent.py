from pipeline.agent.structured_parser import build_structured_with_agent
from pipeline.parser.pdf_parse import Paragraph


class FakeAgent:
    def complete_json(self, *, system: str, user: str):
        assert "source_para_ids" in system
        assert "p1" in user
        return {
            "summary": "Agent summary",
            "concept": "Agent concept",
            "methods": "Agent methods",
            "experiments": "Agent experiments",
            "limitations": ["Agent limitation"],
            "source_para_ids": ["p1", "unknown"],
        }


def test_structured_agent_keeps_only_real_source_ids() -> None:
    result = build_structured_with_agent(
        "agent-paper",
        [Paragraph("p1", 1, "results", "The experiment reports an accuracy result."), Paragraph("p2", 2, "conclusion", "The conclusion describes future work clearly.")],
        title="Agent Paper",
        agent=FakeAgent(),
    )

    assert result.required_ok()
    assert result.source_para_ids == ["p1"]
    assert result.validation_flags == []
