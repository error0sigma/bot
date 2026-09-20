from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Iterable

from .base import Connector, ConnectorContext
from ..models import Entity, Finding, Relationship, stable_id


class GitHubConnector(Connector):
    """Search GitHub public users and repositories using the public GitHub API."""

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
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as res:
            payload = res.read().decode("utf-8", errors="replace")
            return json.loads(payload) if payload else {}

    def search(self, query: str, context: ConnectorContext) -> Iterable[Finding]:
        if not query or query.startswith(("http://", "https://")):
            return []
        q = urllib.parse.quote(query)
        data = self._request(f"{self.base_url}/search/users?q={q}&per_page=5")
        items = data.get("items", [])
        for item in items:
            login = item.get("login", "")
            if not login:
                continue
            prof_id = stable_id("github-user", login)
            entity = Entity(
                prof_id,
                "Profile",
                login,
                {
                    "platform": "github",
                    "login": login,
                    "url": item.get("html_url"),
                    "avatar_url": item.get("avatar_url"),
                    "score": item.get("score"),
                },
                "github",
                0.86,
            )
            rels = [
                Relationship(
                    stable_id("rel", prof_id, "github", "has_profile"),
                    prof_id,
                    prof_id,
                    "has_profile",
                    "github",
                    0.9,
                    attributes={"platform": "github", "url": item.get("html_url")},
                )
            ]
            yield Finding(entity, relationships=rels, source_url=item.get("html_url", ""), attributes={"source": "github"})

        repo_data = self._request(f"{self.base_url}/search/repositories?q={q}&per_page=5")
        for item in repo_data.get("items", []):
            repo_id = stable_id("github-repo", item.get("full_name", ""))
            entity = Entity(
                repo_id,
                "Repository",
                item.get("full_name", ""),
                {
                    "platform": "github",
                    "full_name": item.get("full_name"),
                    "url": item.get("html_url"),
                    "description": item.get("description"),
                    "stargazers_count": item.get("stargazers_count"),
                },
                "github",
                0.82,
            )
            yield Finding(entity, source_url=item.get("html_url", ""), attributes={"source": "github"})
