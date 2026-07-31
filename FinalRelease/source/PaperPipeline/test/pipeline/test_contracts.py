from pipeline.integration.contracts import wiki_to_backend_structured_rows


def test_structured_result_rows_clear_empty_validation_and_optional_sections() -> None:
    rows = wiki_to_backend_structured_rows(
        summary="summary",
        concept="concept",
        methods="methods",
        experiments="experiments",
        limitations=[],
        validation_flags=[],
    )
    by_type = {row["result_type"]: row for row in rows}

    assert by_type["limitations"]["content_json"] == {"items": []}
    assert by_type["validation"]["content_json"] == {"flags": []}
