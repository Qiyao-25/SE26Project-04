"""Unit tests for deterministic smart-search normalization and pagination state."""

from __future__ import annotations

from app.service import search_session_store
from app.service.search_query_normalize import (
    expand_chinese_topics,
    expand_term_aliases,
    extract_arxiv_id,
    extract_author_candidates,
    extract_exclude_terms,
    extract_year_range,
    infer_search_mode,
    paper_matches_excludes,
    resolve_author_hints,
    romanize_chinese_person_name,
    strip_query_fillers,
)


class _Paper:
    def __init__(self, title: str, abstract: str = "") -> None:
        self.title = title
        self.abstract = abstract


def setup_function() -> None:
    search_session_store._SESSIONS.clear()


def teardown_function() -> None:
    search_session_store._SESSIONS.clear()


def test_extract_arxiv_id_handles_prefix_versions_and_non_matches() -> None:
    assert extract_arxiv_id("arXiv: 1706.03762v5") == "1706.03762"
    assert extract_arxiv_id("请找 2501.12345 的论文") == "2501.12345"
    assert extract_arxiv_id("没有编号") is None


def test_strip_fillers_removes_polite_prefix_honorific_and_paper_suffix() -> None:
    assert strip_query_fillers("请帮我找沈备军老师的论文") == "沈备军"
    assert strip_query_fillers("  Transformer   论文 ") == "Transformer"
    assert strip_query_fillers("") == ""


def test_extract_year_range_covers_ranges_boundaries_exact_and_recent() -> None:
    assert extract_year_range("2025 到 2022 年的论文") == (2022, 2025)
    assert extract_year_range("2023 年后大模型") == (2023, None)
    assert extract_year_range("before 2020") == (None, 2020)
    assert extract_year_range("2024 年的论文") == (2024, 2024)
    recent_from, recent_to = extract_year_range("recent years multimodal papers")
    assert recent_to is not None
    assert recent_from == recent_to - 2
    assert extract_year_range("不限制年份") == (None, None)


def test_extract_excludes_and_paper_exclusion_match() -> None:
    terms = extract_exclude_terms("不要综述和 review 的 LoRA 论文")
    assert {"survey", "review", "综述"}.issubset(terms)
    assert extract_exclude_terms("普通查询") == []
    assert paper_matches_excludes(_Paper("A Survey of LoRA"), terms) is True
    assert paper_matches_excludes(_Paper("Low-Rank Adaptation"), terms) is False
    assert paper_matches_excludes(_Paper("Any paper"), []) is False


def test_term_aliases_and_chinese_topics_are_curated_and_deduplicated() -> None:
    canonical, aliases, categories = expand_term_aliases("RAG、检索增强生成与 LLM")
    assert "retrieval augmented generation" in canonical
    assert "large language model" in canonical
    assert aliases.count("RAG") == 1
    assert "cs.CL" in categories
    assert expand_term_aliases("unmapped subject") == ([], [], [])

    topics, topic_categories = expand_chinese_topics("自然语言处理中的多模态和大语言模型")
    assert "natural language processing" in topics
    assert "multimodal" in topics
    assert "large language model" in topics
    assert "cs.CL" in topic_categories
    assert expand_chinese_topics("未知方向") == ([], [])


def test_romanize_handles_known_chinese_english_and_unmappable_names() -> None:
    assert "Beijun Shen" in romanize_chinese_person_name("沈备军")
    assert romanize_chinese_person_name("") == []

    english = romanize_chinese_person_name("Ashish Vaswani")
    assert "Ashish Vaswani" in english
    assert "Vaswani Ashish" in english
    assert "Vaswani" in english

    variants = romanize_chinese_person_name("张伟")
    assert "Wei Zhang" in variants
    assert "Zhang Wei" in variants
    assert romanize_chinese_person_name("甲乙") == []


def test_author_resolution_distinguishes_verified_aliases_and_soft_pinyin() -> None:
    hints, verified, warnings = resolve_author_hints("沈备军教授的论文")
    assert "Beijun Shen" in hints
    assert verified is True
    assert warnings == []

    hints, verified, warnings = resolve_author_hints("张伟老师的论文")
    assert "Wei Zhang" in hints
    assert verified is False
    assert warnings == ["AUTHOR_TRANSLITERATION_UNVERIFIED"]

    hints, verified, warnings = resolve_author_hints("papers by Ashish Vaswani")
    assert "Ashish Vaswani" in hints
    assert verified is True
    assert warnings == []
    assert extract_author_candidates("作者: 张伟")


def test_infer_search_mode_prioritizes_ids_then_author_mixed_and_topic() -> None:
    assert infer_search_mode("arxiv:1706.03762") == "arxiv"
    assert infer_search_mode("找一下沈备军老师的论文") == "author"
    assert infer_search_mode("沈备军关于软件工程的论文") == "mixed"
    assert infer_search_mode("大语言模型的微调方法") == "topic"


def test_search_session_is_retrievable_and_expires() -> None:
    item = search_session_store.create_search_session(
        query="RAG",
        plan={"mode": "topic"},
        paper_ids=[1, 2],
        category="cs.CL",
        ttl_s=60,
    )
    fetched = search_session_store.get_search_session(item.session_id)
    assert fetched is item
    assert fetched.paper_ids == [1, 2]
    assert fetched.category == "cs.CL"
    assert search_session_store.get_search_session(None) is None

    item.expires_at = 0
    assert item.alive() is False
    assert search_session_store.get_search_session(item.session_id) is None


def test_search_session_purges_dead_entries_and_evicts_oldest_when_full(monkeypatch) -> None:
    monkeypatch.setattr(search_session_store, "_MAX_SESSIONS", 3)
    expired = search_session_store.create_search_session(
        query="expired", plan={}, paper_ids=[], ttl_s=0
    )
    search_session_store.create_search_session(query="first", plan={}, paper_ids=[1])
    search_session_store.create_search_session(query="second", plan={}, paper_ids=[2])
    search_session_store.create_search_session(query="third", plan={}, paper_ids=[3])
    search_session_store.create_search_session(query="fourth", plan={}, paper_ids=[4])

    assert expired.session_id not in search_session_store._SESSIONS
    assert len(search_session_store._SESSIONS) <= 3
    assert search_session_store.get_search_session("missing") is None
