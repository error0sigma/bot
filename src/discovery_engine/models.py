from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Entity:
    id: str
    type: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    confidence: float = 0.5
    discovered_at: str = field(default_factory=utc_now)
    last_seen_at: str = field(default_factory=utc_now)


@dataclass
class Relationship:
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    source: str
    confidence: float = 0.5
    discovered_at: str = field(default_factory=utc_now)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    entity: Entity
    relationships: list[Relationship] = field(default_factory=list)
    source_url: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(order=True)
class SearchTask:
    sort_key: tuple[int, int] = field(init=False, repr=False)
    priority: int
    created_seq: int
    entity_id: str = field(compare=False)
    query: str = field(compare=False)
    depth: int = field(compare=False, default=0)
    connector: str | None = field(compare=False, default=None)
    attempts: int = field(compare=False, default=0)
    available_at: float = field(compare=False, default=0.0)
    reason: str = field(compare=False, default="discovery")

    def __post_init__(self) -> None:
        self.sort_key = (-self.priority, self.created_seq)


def stable_id(*parts: str) -> str:
    import hashlib
    value = "|".join(p.strip().lower() for p in parts if p and p.strip())
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default, sort_keys=True)


def _json_default(value: Any) -> Any:
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)
