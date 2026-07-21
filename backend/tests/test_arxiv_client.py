"""Unit tests for arXiv RSS / Atom parsing (no network)."""

from app.service.arxiv_client import ArxivClient, _parse_rss_or_atom


def test_parse_rss_item_extracts_arxiv_id():
    xml = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>cs.CL</title>
        <item>
          <title>Example Paper</title>
          <link>https://arxiv.org/abs/2401.01234</link>
          <guid>https://arxiv.org/abs/2401.01234v1</guid>
          <description>An abstract.</description>
          <category>cs.CL</category>
        </item>
      </channel>
    </rss>
    """
    papers = _parse_rss_or_atom(xml)
    assert len(papers) == 1
    assert papers[0].arxiv_id == "2401.01234"
    assert papers[0].title == "Example Paper"
    assert papers[0].categories == ["cs.CL"]


def test_fetch_category_rss_url_shape():
    client = ArxivClient(rss_base="https://rss.arxiv.org/rss")
    assert client.rss_base.endswith("/rss")
