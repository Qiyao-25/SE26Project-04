from app.schema.papers import WikiData
from app.service.wiki_qa import build_wiki_evidence, wiki_has_content, wiki_item_text


def _wiki(**kwargs) -> WikiData:
    base = {
        "paper_id": 1,
        "parse_status": "completed",
        "summary": "",
        "concepts": [],
        "methods": [],
        "experiments": [],
        "limitations": [],
        "validation_flags": [],
        "source_locator": {},
    }
    base.update(kwargs)
    return WikiData(**base)


def test_wiki_item_text_from_dict() -> None:
    assert "Attention" in wiki_item_text({"name": "Attention", "description": "weights tokens"})


def test_wiki_has_content() -> None:
    assert wiki_has_content(_wiki(parse_status="pending")) is False
    assert wiki_has_content(_wiki(summary="A survey of transformers.")) is True


def test_build_wiki_evidence_prefers_method_for_method_question() -> None:
    wiki = _wiki(
        summary="This paper surveys efficient transformers.",
        concepts=[{"name": "Attention", "description": "token weighting"}],
        methods=[{"title": "Sparse Attention", "description": "uses block-sparse kernels"}],
        experiments=[{"title": "GLUE", "description": "improves latency"}],
        limitations=["limited multilingual coverage"],
    )
    evidence = build_wiki_evidence(wiki, "这篇论文的方法是什么？", top_k=4)
    assert evidence
    assert any(item["chunk_id"].startswith("wiki-method") for item in evidence)
    assert all("section_title" in item and item["source"] == "wiki" for item in evidence)
