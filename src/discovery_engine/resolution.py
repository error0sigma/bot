from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .models import Entity, Finding, stable_id


@dataclass(frozen=True)
class Resolution:
    canonical_id: str
    score: float
    reason: str


class EntityResolver:
    """Conservative, explainable resolver; it never merges on label alone."""

    def resolve(self, entity: Entity, existing: list[dict[str, Any]]) -> Resolution | None:
        aliases = self._values(entity)
        best: Resolution | None = None
        for candidate in existing:
            if candidate["type"] != entity.type:
                continue
            values = self._values_from_row(candidate)
            overlap = aliases & values
            score = 0.0
            reason = ""
            if entity.attributes.get("canonical_url") and entity.attributes.get("canonical_url") in values:
                score, reason = 0.98, "same canonical URL"
            elif overlap:
                score, reason = min(0.95, 0.75 + 0.1 * len(overlap)), "shared normalized identifier"
            elif self.normalize(entity.label) == self.normalize(candidate["label"]):
                score, reason = 0.80, "same normalized label"
            if score >= 0.80 and (best is None or score > best.score):
                best = Resolution(candidate["id"], score, reason)
        return best

    def canonicalize(self, entity: Entity, existing: list[dict[str, Any]]) -> tuple[Entity, Resolution | None]:
        match = self.resolve(entity, existing)
        if not match:
            return entity, None
        merged = dict(entity.attributes)
        row = next(x for x in existing if x["id"] == match.canonical_id)
        old = row.get("attributes", {})
        if isinstance(old, str):
            import json
            old = json.loads(old)
        for key, value in old.items():
            if key not in merged:
                merged[key] = value
        entity.id = match.canonical_id
        entity.attributes = merged
        return entity, match

    @staticmethod
    def normalize(value: str) -> str:
        value = unicodedata.normalize("NFKC", value or "").casefold()
        return re.sub(r"[^\w]+", "", value, flags=re.UNICODE)

    def _values(self, entity: Entity) -> set[str]:
        values = {self.normalize(entity.label)}
        for key, value in entity.attributes.items():
            if key in {"username", "handle", "canonical_url", "url", "email", "login"}:
                if isinstance(value, str): values.add(self.normalize(value))
            elif key in {"usernames", "aliases", "urls", "emails"} and isinstance(value, list):
                values.update(self.normalize(str(x)) for x in value)
        return {x for x in values if x}

    def _values_from_row(self, row: dict[str, Any]) -> set[str]:
        import json
        attrs = row.get("attributes", {})
        if isinstance(attrs, str): attrs = json.loads(attrs)
        return self._values(Entity(row["id"], row["type"], row["label"], attrs))
