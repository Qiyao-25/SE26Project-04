from harness.scenarios import run_agent_scenario, run_e2e_scenario, run_parse_scenario, run_qa_scenario


def test_harness_agent_scenario_uses_stub_and_checks_grounding() -> None:
    result = run_agent_scenario()

    assert result.ok is True
    assert result.checks["structured_fields_present"] is True
    assert result.checks["qa_citation_is_grounded"] is True
    assert result.checks["stub_calls"] == 2


def test_harness_parse_scenario_persists_agent_results() -> None:
    result = run_parse_scenario()

    assert result.ok is True
    assert result.checks["task_succeeded"] is True
    assert result.checks["paper_qa_ready"] is True
    assert result.checks["graph_results_persisted"] is True


def test_harness_qa_scenario_rejects_unverified_citations() -> None:
    result = run_qa_scenario()

    assert result.ok is True
    assert result.checks["citation_from_evidence"] is True


def test_harness_e2e_scenario_runs_parse_and_qa() -> None:
    result = run_e2e_scenario()

    assert result.ok is True
    assert result.checks["parse"]["ok"] is True
    assert result.checks["qa"]["ok"] is True
