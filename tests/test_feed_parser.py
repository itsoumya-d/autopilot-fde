"""RSS 2.0 and Atom ingestion for media/publishing feeds."""

from datetime import UTC, datetime

import pytest

from backend.ingestion.feed_parser import FeedParseError, parse_feed

RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Example News</title>
    <item>
      <guid>story-1</guid>
      <title>Story &amp; One</title>
      <link>https://example.com/story-1</link>
      <description>Summary &lt;b&gt;one&lt;/b&gt;</description>
      <pubDate>Tue, 28 Oct 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <guid>story-2</guid>
      <title>Story Two</title>
      <link>https://example.com/story-2</link>
      <description>Summary two</description>
      <pubDate>Wed, 29 Oct 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>atom-1</id>
    <title>Atom One</title>
    <link href="https://example.com/atom-1"/>
    <summary>Atom summary</summary>
    <published>2026-10-28T10:00:00Z</published>
  </entry>
  <entry>
    <id>atom-2</id>
    <title>Atom Two</title>
    <link rel="alternate" href="https://example.com/atom-2"/>
    <content>Content two</content>
    <updated>2026-10-29T10:00:00Z</updated>
  </entry>
</feed>"""


def test_parse_rss_items() -> None:
    items = parse_feed(RSS, source="Allied Media")

    assert len(items) == 2
    assert items[0].id == "story-1"
    assert items[0].title == "Story & One"
    assert items[0].link == "https://example.com/story-1"
    assert items[0].summary == "Summary <b>one</b>"
    assert items[0].source == "Allied Media"
    assert items[0].published_at == datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


def test_parse_atom_entries() -> None:
    items = parse_feed(ATOM, source="Allied Media")

    assert len(items) == 2
    assert items[0].id == "atom-1"
    assert items[0].title == "Atom One"
    assert items[0].link == "https://example.com/atom-1"
    assert items[0].summary == "Atom summary"
    assert items[0].published_at == datetime(2026, 10, 28, 10, 0, tzinfo=UTC)
    assert items[1].summary == "Content two"


def test_missing_fields_use_fallback_id() -> None:
    xml = """<rss><channel><item><title>Only a title</title></item></channel></rss>"""

    items = parse_feed(xml, source="Source")

    assert len(items) == 1
    assert items[0].id
    assert len(items[0].id) == 16
    assert items[0].title == "Only a title"
    assert items[0].link == ""
    assert items[0].summary == ""
    assert items[0].published_at is None


def test_empty_title_gets_fallback() -> None:
    xml = """<rss><channel><item><guid>g</guid><title/></item></channel></rss>"""

    items = parse_feed(xml, source="Source")

    assert items[0].title == "Untitled"


def test_deduplicates_by_id() -> None:
    xml = """<rss><channel>
      <item><guid>same</guid><title>One</title></item>
      <item><guid>same</guid><title>Two</title></item>
    </channel></rss>"""

    items = parse_feed(xml, source="Source")

    assert len(items) == 1
    assert items[0].title == "One"


def test_filters_by_since() -> None:
    since = datetime(2026, 10, 29, 0, 0, tzinfo=UTC)

    items = parse_feed(RSS, source="Source", since=since)

    assert len(items) == 1
    assert items[0].id == "story-2"


def test_undated_item_is_kept_by_since_filter() -> None:
    xml = """<rss><channel><item><guid>undated</guid><title>Undated</title></item></channel></rss>"""

    items = parse_feed(xml, source="Source", since=datetime(2030, 1, 1, tzinfo=UTC))

    assert len(items) == 1


def test_invalid_dates_become_none() -> None:
    rss = """<rss><channel><item><guid>r</guid><pubDate>not-a-date</pubDate></item></channel></rss>"""
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>a</id><published>not-a-date</published></entry></feed>"""

    assert parse_feed(rss, source="Source")[0].published_at is None
    assert parse_feed(atom, source="Source")[0].published_at is None


def test_atom_naive_date_is_treated_as_utc() -> None:
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>a</id><updated>2026-10-28T10:00:00</updated></entry></feed>"""

    items = parse_feed(atom, source="Source")

    assert items[0].published_at == datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


def test_atom_without_link() -> None:
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>a</id></entry></feed>"""

    items = parse_feed(atom, source="Source")

    assert items[0].link == ""


def test_empty_rss_channel_and_atom_feed() -> None:
    assert parse_feed("<rss><channel/></rss>", source="Source") == []
    assert parse_feed('<feed xmlns="http://www.w3.org/2005/Atom"/>', source="Source") == []
    assert parse_feed("<rss/>", source="Source") == []


@pytest.mark.parametrize("xml", ["", "   ", "<rss>", "<html></html>"])
def test_invalid_or_unsupported_feeds_raise(xml: str) -> None:
    with pytest.raises(FeedParseError):
        parse_feed(xml, source="Source")
