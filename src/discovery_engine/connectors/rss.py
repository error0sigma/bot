from __future__ import annotations

import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from typing import Iterable

from .base import Connector, ConnectorContext
from ..models import Entity, Finding, Relationship, stable_id


class RSSConnector(Connector):
    """Read public RSS feeds and translate items into disclosure-worthy entities."""

    name = "rss"
    entity_types = {"Publication", "News", "Event"}
    relationship_types = {"mentions", "published_in"}

    def __init__(self, feeds: list[str] | None = None):
        self.feeds = feeds or []

    def can_handle(self, task_query: str) -> bool:
        query = (task_query or "").strip()
        return query.startswith(("http://", "https://")) or query.lower().endswith(".rss") or query.lower().endswith(".xml")

    def _fetch_feed(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "public-discovery-engine/0.2"})
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.read().decode("utf-8", errors="replace")

    def search(self, query: str, context: ConnectorContext) -> Iterable[Finding]:
        urls = [query] if self.can_handle(query) else list(self.feeds)
        if not urls:
            return []
        for url in urls:
            try:
                text = self._fetch_feed(url)
            except Exception:
                continue
            root = ET.fromstring(text)
            ns = {"": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//item") or root.findall(".//entry")
            for item in items:
                title = (item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or "Untitled").strip()
                link = item.findtext("link") or item.findtext("{http://www.w3.org/2005/Atom}link") or url
                pub_date = item.findtext("pubDate") or item.findtext("{http://www.w3.org/2005/Atom}updated") or ""
                entity = Entity(
                    stable_id("rss", title, link),
                    "Publication",
                    title,
                    {"source_url": link, "published_at": pub_date, "feed_url": url},
                    "rss",
                    0.71,
                )
                yield Finding(entity, source_url=link, attributes={"feed_url": url, "published_at": pub_date})
        return []
