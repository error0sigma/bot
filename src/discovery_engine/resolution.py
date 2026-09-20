from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .models import Entity


@dataclass(frozen=True)
class Resolution:
    canonical_id: str
    score: float
    reason: str


class EntityResolver:
    """Conservative, explainable merging logic for entities with shared identifiers."""

    def resolve(self, entity: Entity, existing: list[dict[str, Any]]) -> Resolution | None:
        aliases = self._values(entity)
        best: Resolution | None = None
        for candidate in existing:
            if candidate.get("type") != entity.type:
                continue
            candidate_values = self._values_from_row(candidate)
            overlap = aliases & candidate_values
            score = 0.0
            reason = ""
            if entity.attributes.get("canonical_url") and entity.attributes.get("canonical_url") in candidate_values:
                score, reason = 0.98, "same canonical URL"
            elif overlap:
                score, reason = min(0.95, 0.75 + 0.1 * len(overlap)), "shared normalized identifier"
            elif self.normalize(entity.label) == self.normalize(candidate.get("label", "")):
                score, reason = 0.80, "same normalized label"

            if score >= 0.80 and (best is None or score > best.score):
                best = Resolution(candidate["id"], score, reason)
        return best

    def canonicalize(self, entity: Entity, existing: list[dict[str, Any]]) -> tuple[Entity, Resolution | None]:
        match = self.resolve(entity, existing)
        if not match:
            return entity, None
        row = next(item for item in existing if item["id"] == match.canonical_id)
        merged = dict(entity.attributes)
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
            if key in {"username", "handle", "canonical_url", "url", "email", "login"} and isinstance(value, str):
                values.add(self.normalize(value))
            elif key in {"usernames", "aliases", "urls", "emails"} and isinstance(value, list):
                values.update(self.normalize(str(v)) for v in value)
        return {v for v in values if v}

    def _values_from_row(self, row: dict[str, Any]) -> set[str]:
        attrs = row.get("attributes", {})
        if isinstance(attrs, str):
            import json
            attrs = json.loads(attrs)
        return self._values(Entity(row["id"], row["type"], row["label"], attrs))
