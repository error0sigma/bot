from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from .base import Sink


class GoogleSheetsSink(Sink):
    """Simple sink for pushing snapshots to a Google Apps Script webhook or any JSON endpoint."""

    name = "google_sheets"

    def __init__(self, webhook_url: str | None = None, path: str | None = None):
        self.webhook_url = webhook_url or os.getenv("DISCOVERY_SHEETS_WEBHOOK_URL")
        self.path = path or os.getenv("DISCOVERY_SHEETS_PATH")

    def publish(self, snapshot: dict[str, Any]) -> None:
        payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
        if self.webhook_url:
            req = urllib.request.Request(
                self.webhook_url,
                data=payload.encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "public-discovery-engine/0.2"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=20):
                    return
            except Exception:
                pass
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(payload + "\n")
