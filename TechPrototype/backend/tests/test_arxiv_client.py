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


def test_parse_rss_splits_long_creator_blob():
    long_authors = ", ".join([f"Author{i} Name" for i in range(30)])
    assert len(long_authors) > 255
    xml = f"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Many Authors</title>
          <guid>oai:arXiv.org:2501.99999</guid>
          <link>https://arxiv.org/abs/2501.99999</link>
          <description>abs</description>
          <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">{long_authors}</dc:creator>
        </item>
      </channel>
    </rss>
    """.encode("utf-8")
    papers = _parse_rss_or_atom(xml)
    assert len(papers) == 1
    assert papers[0].arxiv_id == "2501.99999"
    assert len(papers[0].authors) > 1
    assert all(len(name) <= 255 for name in papers[0].authors)


def test_fetch_category_rss_url_shape():
    client = ArxivClient(rss_base="https://rss.arxiv.org/rss")
    assert client.rss_base.endswith("/rss")
