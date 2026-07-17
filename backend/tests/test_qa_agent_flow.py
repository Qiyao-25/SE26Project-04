from app.service.qa import answer_with_agent


class FakeAgent:
    def __init__(self, result):
        self.result = result

    def run(self, **_kwargs):
        return self.result


def test_agent_answer_keeps_only_known_citations(monkeypatch) -> None:
    from app.agents.qa_agent import QaAgentResult
    import app.service.qa as qa

    monkeypatch.setattr(qa, "get_settings", lambda: type("Settings", (), {"qa_agent_ready": True})())
    monkeypatch.setattr(qa, "QaAgent", lambda _settings: FakeAgent(QaAgentResult("The method uses attention.", ["c1"], False)))
    result = answer_with_agent(
        question="What is the method?",
        evidence=[{"chunk_id": "c1", "content": "The method uses attention."}],
        fallback="fallback",
        settings=type("Settings", (), {"qa_agent_ready": True})(),
    )
    assert result.answer == "The method uses attention."
    assert result.citation_ids == ["c1"]


def test_invalid_agent_citation_falls_back_to_evidence(monkeypatch) -> None:
    from app.agents.qa_agent import QaAgentResult
    import app.service.qa as qa

    monkeypatch.setattr(qa, "get_settings", lambda: type("Settings", (), {"qa_agent_ready": True})())
    monkeypatch.setattr(qa, "QaAgent", lambda _settings: FakeAgent(QaAgentResult("unsupported", ["unknown"], False)))
    result = answer_with_agent(
        question="What is the method?",
        evidence=[{"chunk_id": "c1", "content": "The method uses attention."}],
        fallback="evidence fallback",
        settings=type("Settings", (), {"qa_agent_ready": True})(),
    )
    assert result.answer == "evidence fallback"
    assert result.citation_ids == ["c1"]
