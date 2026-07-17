from pathlib import Path

from pipeline.parser.html_parse import parse_html_file


def test_arxiv_html_parser_extracts_sections_and_text(tmp_path: Path) -> None:
    html = tmp_path / "1706.03762.html"
    html.write_text(
        """
        <html><body>
          <h2>1 Introduction</h2>
          <p>The Transformer uses attention to connect tokens without recurrence.</p>
          <h2>3 Experiments</h2>
          <p>We evaluate the model on translation benchmarks and report measurable results.</p>
          <script>ignore this script content</script>
        </body></html>
        """,
        encoding="utf-8",
    )

    result = parse_html_file("1706.03762", html, min_chars=80)

    assert result.ok is True
    assert result.source_type == "html"
    assert result.page_count == 1
    assert len(result.paragraphs) == 2
    assert result.paragraphs[0].section == "introduction"
    assert "ignore this script" not in result.paragraphs[1].text
