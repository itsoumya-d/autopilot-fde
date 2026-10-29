"""RSS 2.0 and Atom ingestion for publishing and media feeds."""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

ATOM_NS = "{http://www.w3.org/2005/Atom}"


class FeedParseError(ValueError):
    """Raised when a feed cannot be parsed or is not RSS/Atom."""


@dataclass(frozen=True)
class FeedItem:
    id: str
    title: str
    link: str
    summary: str
    source: str
    published_at: datetime | None


def parse_feed(xml_text: str, source: str, since: datetime | None = None) -> list[FeedItem]:
    if not xml_text.strip():
        raise FeedParseError("feed is empty")

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise FeedParseError("feed is not valid XML") from exc

    if root.tag == "rss":
        items = _parse_rss_items(root, source)
    elif root.tag == f"{ATOM_NS}feed":
        items = _parse_atom_entries(root, source)
    else:
        raise FeedParseError("feed must be RSS 2.0 or Atom")

    deduped: list[FeedItem] = []
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            continue
        if since is not None and item.published_at is not None and item.published_at < since:
            continue
        seen.add(item.id)
        deduped.append(item)

    return deduped


def _parse_rss_items(root: ElementTree.Element, source: str) -> list[FeedItem]:
    channel = root.find("channel")
    if channel is None:
        return []

    items: list[FeedItem] = []
    for item in channel.findall("item"):
        title = _text(item, "title")
        link = _text(item, "link")
        guid = _text(item, "guid")
        summary = html.unescape(_text(item, "description"))
        published_at = _parse_rss_date(_text(item, "pubDate"))
        item_id = guid or link or _fallback_id(title, published_at)
        items.append(
            FeedItem(
                id=item_id,
                title=title or "Untitled",
                link=link,
                summary=summary,
                source=source,
                published_at=published_at,
            )
        )
    return items


def _parse_atom_entries(root: ElementTree.Element, source: str) -> list[FeedItem]:
    items: list[FeedItem] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        title = _text(entry, f"{ATOM_NS}title")
        link = _atom_link(entry)
        entry_id = _text(entry, f"{ATOM_NS}id")
        summary = html.unescape(_text(entry, f"{ATOM_NS}summary") or _text(entry, f"{ATOM_NS}content"))
        published_at = _parse_atom_date(
            _text(entry, f"{ATOM_NS}published") or _text(entry, f"{ATOM_NS}updated")
        )
        item_id = entry_id or link or _fallback_id(title, published_at)
        items.append(
            FeedItem(
                id=item_id,
                title=title or "Untitled",
                link=link,
                summary=summary,
                source=source,
                published_at=published_at,
            )
        )
    return items


def _text(parent: ElementTree.Element, child: str) -> str:
    element = parent.find(child)
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _atom_link(entry: ElementTree.Element) -> str:
    for link in entry.findall(f"{ATOM_NS}link"):
        if link.get("rel", "alternate") == "alternate":
            return link.get("href", "")
    return ""


def _parse_rss_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return _as_utc(parsed)


def _parse_atom_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _fallback_id(title: str, published_at: datetime | None) -> str:
    seed = f"{title}|{published_at.isoformat() if published_at else ''}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
