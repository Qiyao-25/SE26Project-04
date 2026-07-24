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
        settings=type("Settings", (), {"qa_agent_ready": True})(),
    )
    assert result.answer == "The method uses attention."
    assert result.citation_ids == ["c1"]


def test_invalid_agent_citation_is_refused(monkeypatch) -> None:
    from app.agents.qa_agent import QaAgentResult
    import app.service.qa as qa

    monkeypatch.setattr(qa, "get_settings", lambda: type("Settings", (), {"qa_agent_ready": True})())
    monkeypatch.setattr(qa, "QaAgent", lambda _settings: FakeAgent(QaAgentResult("unsupported", ["unknown"], False)))
    result = answer_with_agent(
        question="What is the method?",
        evidence=[{"chunk_id": "c1", "content": "The method uses attention."}],
        settings=type("Settings", (), {"qa_agent_ready": True})(),
    )
    assert result.answer == "unsupported"
    assert result.citation_ids == []
    assert result.refused is True


def test_agent_parses_string_false_as_false(monkeypatch) -> None:
    import app.agents.qa_agent as qa_agent

    monkeypatch.setattr(
        qa_agent,
        "chat_completion",
        lambda **_kwargs: '{"answer":"The method uses attention.","evidence_ids":["E1"],"refuse":"false"}',
    )
    result = qa_agent.QaAgent(type("Settings", (), {
        "llm_api_key": "test-key",
        "llm_api_base": "https://example.com/v1",
        "llm_model": "test-model",
        "qa_agent_timeout_s": 1,
    })()).run(
        title="Test paper",
        question="What is the method?",
        evidence=[{"chunk_id": "c1", "content": "The method uses attention."}],
    )
    assert result.refuse is False


def test_agent_parses_query_plan(monkeypatch) -> None:
    import app.agents.qa_agent as qa_agent

    monkeypatch.setattr(
        qa_agent,
        "chat_completion",
        lambda **_kwargs: '{"paper_related":true,"search_queries":["lightweight transformer survey","edge deployment findings"]}',
    )
    result = qa_agent.QaAgent(type("Settings", (), {
        "llm_api_key": "test-key",
        "llm_api_base": "https://example.com/v1",
        "llm_model": "test-model",
        "qa_agent_timeout_s": 1,
    })()).rewrite_query(
        title="Lightweight Transformers",
        abstract="A survey of efficient models.",
        question="What is the main contribution?",
    )
    assert result.paper_related is True
    assert result.search_queries == ["lightweight transformer survey", "edge deployment findings"]
