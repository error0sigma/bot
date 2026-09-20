from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Iterable

from .base import Connector, ConnectorContext
from ..models import Entity, Finding, stable_id


class SearchAPIConnector(Connector):
    """Generic REST-based search API connector; intended to plug into a provider such as SerpAPI, Bing, or a private proxy."""

    name = "search_api"
    entity_types = {"Person", "Profile", "Organization", "Publication"}
    relationship_types = {"mentioned_in"}

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.getenv("SEARCH_API_URL") or "").rstrip("/")
        self.api_key = api_key or os.getenv("SEARCH_API_KEY")

    def can_handle(self, task_query: str) -> bool:
        return bool(self.base_url)

    def search(self, query: str, context: ConnectorContext) -> Iterable[Finding]:
        if not self.base_url or not query:
            return []
        params = {"q": query, "key": self.api_key} if self.api_key else {"q": query}
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "public-discovery-engine/0.2"})
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                payload = json.loads(res.read().decode("utf-8", errors="replace"))
        except Exception:
            return []
        for item in payload.get("results", payload.get("items", [])):
            title = item.get("title") or item.get("name") or "Unknown result"
            url_value = item.get("url") or item.get("html_url") or item.get("link") or ""
            entity = Entity(
                stable_id("search", title, url_value),
                item.get("type") or "Publication",
                title,
                {"source": "search_api", "search_query": query, "snippet": item.get("snippet") or item.get("description")},
                "search_api",
                0.74,
            )
            yield Finding(entity, source_url=url_value, attributes={"source": "search_api"})
        return []
