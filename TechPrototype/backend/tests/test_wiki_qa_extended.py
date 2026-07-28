"""Extended wiki QA branch coverage."""

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


def test_wiki_item_text_branches() -> None:
    assert wiki_item_text(None) == ""
    assert wiki_item_text("plain") == "plain"
    assert wiki_item_text({"title": "Method", "description": "desc"}) == "Method\ndesc"
    assert wiki_item_text(123) == "123"


def test_wiki_has_content_from_groups() -> None:
    assert wiki_has_content(_wiki(methods=[{"title": "M", "description": "method body"}])) is True
    assert wiki_has_content(_wiki(experiments=[{"title": "E", "description": "exp"}])) is True
    assert wiki_has_content(_wiki(limitations=["future work"])) is True
    assert wiki_has_content(_wiki(concepts=[{"name": "", "description": ""}])) is False


def test_build_wiki_evidence_question_boosts() -> None:
    wiki = _wiki(
        summary="Overview of the paper.",
        concepts=[{"name": "Concept", "description": "definition text"}],
        methods=[{"title": "Method", "description": "architecture details"}],
        experiments=[{"title": "Bench", "description": "accuracy gains"}],
        limitations=["limited data"],
    )
    concept_hits = build_wiki_evidence(wiki, "概念定义是什么", top_k=5)
    method_hits = build_wiki_evidence(wiki, "实验结果如何", top_k=5)
    limit_hits = build_wiki_evidence(wiki, "局限和未来工作", top_k=5)
    assert any(item["chunk_id"].startswith("wiki-concept") for item in concept_hits)
    assert any(item["chunk_id"].startswith("wiki-experiment") for item in method_hits)
    assert any(item["chunk_id"].startswith("wiki-limitation") for item in limit_hits)

    empty = build_wiki_evidence(_wiki(), "anything", top_k=3)
    assert empty == []
