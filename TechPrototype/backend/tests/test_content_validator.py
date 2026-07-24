from app.service.content_validator import ContentValidationAgent
from app.service.dedupe import normalize_title


def test_content_validation_marks_uncertain_fields() -> None:
    report = ContentValidationAgent().validate_wiki(
        summary="短",
        concepts=[],
        methods=[],
        experiments=[{"title": "实验", "description": "需结合原文核对"}],
        limitations=["建议人工复核"],
        page_count=0,
        body_chars=50,
        existing_flags=["agent_unavailable"],
        source="heuristic_fallback",
    )
    assert "low_confidence_summary" in report.flags or "missing_concepts" in report.flags
    assert "experiments" in report.uncertain_fields
    assert report.issues


def test_normalize_title_dedupes_punctuation() -> None:
    assert normalize_title("Attention Is All You Need!") == normalize_title("attention is all you need")
