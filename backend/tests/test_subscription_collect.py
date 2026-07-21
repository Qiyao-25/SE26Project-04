"""Unit tests for subscription new-paper collection (no network)."""

from app.service.arxiv_client import ArxivPaperMeta
from app.service.subscriptions import _collect_new_metas


def _meta(arxiv_id: str, title: str | None = None) -> ArxivPaperMeta:
    return ArxivPaperMeta(
        arxiv_id=arxiv_id,
        title=title or f"Title {arxiv_id}",
        authors=["A"],
        abstract="abs",
        categories=["cs.LG"],
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        published="2024-01-01T00:00:00Z",
    )


class FakeClient:
    def __init__(self, pages: list[list[ArxivPaperMeta]], rss: list[ArxivPaperMeta] | None = None):
        self.pages = pages
        self.rss = rss or []
        self.search_calls: list[dict] = []

    def fetch_category_rss(self, category: str, *, max_results: int = 5):
        return self.rss[:max_results]

    def search(self, *, search_query: str, max_results: int = 5, start: int = 0, sort_by: str = "submittedDate"):
        self.search_calls.append({"start": start, "max_results": max_results, "query": search_query})
        page = start // max(max_results, 1)
        if page >= len(self.pages):
            return []
        return self.pages[page][:max_results]


def test_collect_skips_known_and_paginates_for_new():
    client = FakeClient(
        rss=[_meta("2401.00001"), _meta("2401.00002")],
        pages=[
            [_meta("2401.00001"), _meta("2401.00002"), _meta("2401.00003")],
            [_meta("2401.00004"), _meta("2401.00005")],
        ],
    )
    existing = {"2401.00001", "2401.00002"}
    batch: set[str] = set()
    item = {"type": "category", "value": "cs.LG"}
    metas, skipped = _collect_new_metas(
        client,
        item,
        want=2,
        existing_ids=existing,
        batch_seen_ids=batch,
        page_size=3,
        max_pages=4,
    )
    assert [m.arxiv_id for m in metas] == ["2401.00003", "2401.00004"]
    assert skipped >= 2
    assert client.search_calls  # fell through to API after RSS only had known ids


def test_collect_keyword_uses_api_pages():
    client = FakeClient(
        pages=[
            [_meta("2501.00001"), _meta("2501.00002")],
            [_meta("2501.00003")],
        ]
    )
    metas, skipped = _collect_new_metas(
        client,
        {"type": "keyword", "value": "Transformer"},
        want=3,
        existing_ids={"2501.00001"},
        batch_seen_ids=set(),
        page_size=2,
        max_pages=3,
    )
    assert [m.arxiv_id for m in metas] == ["2501.00002", "2501.00003"]
    assert skipped == 1
