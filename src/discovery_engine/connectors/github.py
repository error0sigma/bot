from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Iterable

from .base import Connector, ConnectorContext
from ..models import Entity, Finding, Relationship, stable_id


class GitHubConnector(Connector):
    """Public GitHub API connector."""

    name = "github"
    entity_types = {"Person", "Organization", "Repository", "Profile"}
    relationship_types = {"has_profile", "contributes_to", "owns"}

    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com"):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")

    def _request(self, url: str) -> dict:
        headers = {"User-Agent": "public-discovery-engine/0.2", "Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return json.loads(payload) if payload else {}

    def search(self, query: str, context: ConnectorContext) -> Iterable[Finding]:
        if not query or query.startswith(("http://", "https://")):
            return []
        q = urllib.parse.quote(query)
        user_data = self._request(f"{self.base_url}/search/users?q={q}&per_page=5")
        for item in user_data.get("items", []):
            login = item.get("login")
            if not login:
                continue
            entity = Entity(
                stable_id("github-user", login),
                "Profile",
                login,
                {"platform": "github", "login": login, "url": item.get("html_url"), "avatar_url": item.get("avatar_url")},
                "github",
                0.86,
            )
            relationships = [
                Relationship(
                    stable_id("rel", entity.id, "github", "has_profile"),
                    entity.id,
                    entity.id,
                    "has_profile",
                    "github",
                    0.9,
                    attributes={"platform": "github", "url": item.get("html_url")},
                )
            ]
            yield Finding(entity, relationships=relationships, source_url=item.get("html_url", ""), attributes={"source": "github"})

        repo_data = self._request(f"{self.base_url}/search/repositories?q={q}&per_page=5")
        for item in repo_data.get("items", []):
            full_name = item.get("full_name")
            if not full_name:
                continue
            entity = Entity(
                stable_id("github-repo", full_name),
                "Repository",
                full_name,
                {"platform": "github", "full_name": full_name, "description": item.get("description"), "url": item.get("html_url")},
                "github",
                0.82,
            )
            yield Finding(entity, source_url=item.get("html_url", ""), attributes={"source": "github"})
