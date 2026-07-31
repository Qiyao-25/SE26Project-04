from pathlib import Path

from pipeline.parser.pdf_parse import extract_paragraphs
from pipeline.summarizer.struct_summary import build_structured


def test_attention_pdf_detects_result_and_conclusion_sections() -> None:
    pdf = Path(__file__).parents[2] / "data" / "worker_pdfs" / "1706.03762.pdf"

    paragraphs, page_count = extract_paragraphs(pdf)
    sections = {paragraph.section for paragraph in paragraphs}
    structured = build_structured("1706.03762", paragraphs, title="Attention Is All You Need")

    assert page_count == 15
    assert "results" in sections
    assert "conclusion" in sections
    assert structured.required_ok()
    assert "experiments_section_not_detected" not in structured.validation_flags
    assert "limitations_not_detected" not in structured.validation_flags
