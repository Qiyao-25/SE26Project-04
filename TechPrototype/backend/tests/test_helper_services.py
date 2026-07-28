"""Unit tests for small helper services."""

from app.schema.papers import WikiData
from app.service.content_validator import ContentValidationAgent
from app.service.dedupe import normalize_arxiv_id, normalize_title
from app.service.qa_citations import (
    build_retrieval_query,
    expand_query_tokens,
    is_noisy_chunk,
    polish_quote,
    score_chunk,
    section_label,
    select_relevant_chunk_ids,
)
from app.service.search_query_normalize import (
    extract_arxiv_id,
    extract_exclude_terms,
    infer_search_mode,
    resolve_author_hints,
    strip_query_fillers,
)
from app.service.wiki_qa import build_wiki_evidence, wiki_has_content, wiki_item_text


def test_dedupe_helpers() -> None:
    assert normalize_arxiv_id("https://arxiv.org/abs/1706.03762v5") == "1706.03762"
    assert normalize_arxiv_id("oai:arXiv.org:2401.00001") == "2401.00001"
    assert normalize_title("Attention Is All You Need!") == normalize_title("attention is all you need")


def test_content_validator_flags() -> None:
    report = ContentValidationAgent().validate_wiki(
        summary="",
        concepts=[],
        methods=[],
        experiments=[],
        limitations=[],
        page_count=0,
        body_chars=10,
        existing_flags=["agent_unavailable"],
        source="heuristic_fallback",
    )
    assert "missing_summary" in report.flags
    assert report.uncertain_fields


def test_search_query_normalize_helpers() -> None:
    assert extract_arxiv_id("arxiv:2501.12345v2") == "2501.12345"
    assert strip_query_fillers("请帮我找 Transformer 论文") == "Transformer"
    hints, verified, _warnings = resolve_author_hints("找一下沈备军的论文")
    assert verified is True
    assert hints
    assert infer_search_mode("1706.03762") == "arxiv"
    assert extract_exclude_terms("不要综述 survey")


def test_wiki_qa_and_qa_citations() -> None:
    assert wiki_item_text({"name": "Attention", "description": "weights"}) == "Attention\nweights"
    wiki = WikiData(
        paper_id=1,
        parse_status="completed",
        summary="Survey of transformers.",
        concepts=[{"name": "Attention", "description": "token weighting"}],
        methods=[{"title": "Sparse Attention", "description": "block sparse kernels"}],
        experiments=[{"title": "GLUE", "description": "improves latency"}],
        limitations=["limited coverage"],
        validation_flags=[],
        source_locator={},
    )
    assert wiki_has_content(wiki) is True
    evidence = build_wiki_evidence(wiki, "方法是什么", top_k=3)
    assert evidence
    assert score_chunk("attention model", "The attention model uses self-attention.") > 0
    assert expand_query_tokens("方法")
    assert build_retrieval_query("它呢？", [{"role": "user", "content": "attention method"}]) != "它呢？"
    assert is_noisy_chunk("permission to reproduce this article") is True
    assert polish_quote("Short." * 30, answer="Short", max_len=40)
    assert section_label("method", "We propose an attention model.")
    selected = select_relevant_chunk_ids(
        answer="attention model architecture",
        evidence=[{"chunk_id": "c1", "content": "The attention model architecture is novel."}],
    )
    assert selected == ["c1"]
