from __future__ import annotations

import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from typing import Iterable

from .base import Connector, ConnectorContext
from ..models import Entity, Finding, stable_id


class RSSConnector(Connector):
    """RSS/news feed connector."""

    name = "rss"
    entity_types = {"Publication", "News", "Event"}
    relationship_types = {"mentions", "published_in"}

    def __init__(self, feeds: list[str] | None = None):
        self.feeds = feeds or []

    def can_handle(self, task_query: str) -> bool:
        q = (task_query or "").strip()
        return q.startswith(("http://", "https://")) or q.lower().endswith(".rss") or q.lower().endswith(".xml")

    def _fetch(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "public-discovery-engine/0.2"})
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")

    def search(self, query: str, context: ConnectorContext) -> Iterable[Finding]:
        urls = [query] if self.can_handle(query) else self.feeds
        if not urls:
            return []
        for url in urls:
            try:
                xml_text = self._fetch(url)
            except Exception:
                continue
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                continue
            items = root.findall(".//item") or root.findall(".//entry")
            for item in items:
                title = (item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or "Untitled").strip()
                link = item.findtext("link") or item.findtext("{http://www.w3.org/2005/Atom}link") or url
                pub_date = item.findtext("pubDate") or item.findtext("{http://www.w3.org/2005/Atom}updated") or ""
                yield Finding(
                    Entity(
                        stable_id("rss", title, link),
                        "Publication",
                        title,
                        {"source_url": link, "published_at": pub_date, "feed_url": url},
                        "rss",
                        0.71,
                    ),
                    source_url=link,
                    attributes={"feed_url": url, "published_at": pub_date},
                )
        return []
