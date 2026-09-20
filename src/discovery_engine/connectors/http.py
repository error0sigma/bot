from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import defaultdict
from typing import Iterable
from .base import Connector, ConnectorContext
from ..models import Entity, Finding, stable_id


class PublicHttpConnector(Connector):
    """Generic opt-in HTTP connector. It extracts no hidden/private data."""
    name = "public_http"

    def __init__(self, allowed_domains: list[str], user_agent: str, requests_per_minute: int = 30,
                 respect_robots_txt: bool = True, max_response_bytes: int = 2_000_000):
        self.allowed_domains = {d.lower() for d in allowed_domains}
        self.user_agent = user_agent
        self.rpm = max(1, requests_per_minute)
        self.respect_robots = respect_robots_txt
        self.max_bytes = max_response_bytes
        self._last_request: dict[str, float] = defaultdict(float)
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _allowed(self, url: str) -> bool:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        return bool(host and (not self.allowed_domains or host in self.allowed_domains or
                              any(host.endswith("." + d) for d in self.allowed_domains)))

    def fetch(self, url: str) -> tuple[str, str]:
        if not self._allowed(url):
            raise PermissionError("domain is not in the connector allowlist")
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        delay = 60.0 / self.rpm
        wait = delay - (time.time() - self._last_request[host])
        if wait > 0:
            time.sleep(wait)
        if self.respect_robots:
            rp = self._robots.get(host)
            if rp is None:
                rp = urllib.robotparser.RobotFileParser(f"{parsed.scheme}://{host}/robots.txt")
                try: rp.read()
                except OSError: pass
                self._robots[host] = rp
            if not rp.can_fetch(self.user_agent, url):
                raise PermissionError("robots.txt disallows this request")
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                raise ValueError("response exceeds configured size limit")
            self._last_request[host] = time.time()
            return data.decode("utf-8", errors="replace"), response.geturl()

    def search(self, query: str, context: ConnectorContext) -> Iterable[Finding]:
        # URLs can be explicitly seeded; arbitrary web-wide crawling is intentionally not implicit.
        if not query.startswith(("http://", "https://")):
            return []
        text, final_url = self.fetch(query)
        entity = Entity(stable_id("web", final_url), "Website", final_url,
                        {"content_preview": text[:1000], "content_length": len(text)},
                        final_url, 0.6)
        return [Finding(entity, source_url=final_url)]
