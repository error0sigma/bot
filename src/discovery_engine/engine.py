from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .models import Entity, Finding
from .queue import DiscoveryQueue
from .storage import GraphStore
from .connectors import Connector, ConnectorContext, Sink
from .resolution import EntityResolver


class Limits:
    def __init__(self, **kwargs: Any):
        self.max_depth = kwargs.get("max_depth", 2)
        self.max_sources = kwargs.get("max_sources", 50)
        self.max_requests_per_source = kwargs.get("max_requests_per_source", 20)
        self.max_runtime = kwargs.get("max_runtime", 300)
        self.confidence_threshold = kwargs.get("confidence_threshold", 0.55)
        self.retry_count = kwargs.get("retry_count", 3)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Limits":
        return cls(**value)


class DiscoveryEngine:
    def __init__(self, store: GraphStore, limits: Limits | None = None, resolver: EntityResolver | None = None):
        self.store = store
        self.limits = limits or Limits()
        self.resolver = resolver or EntityResolver()
        self.queue = DiscoveryQueue()
        self.connectors: dict[str, Connector] = {}
        self.sinks: dict[str, Sink] = {}

    def register_connector(self, connector: Connector) -> None:
        self.connectors[connector.name] = connector

    def register_sink(self, sink: Sink) -> None:
        self.sinks[sink.name] = sink

    def seed(self, query: str, entity_type: str = "SearchSeed", priority: int = 100) -> str:
        from .models import stable_id

        entity_id = stable_id(entity_type, query)
        entity = Entity(entity_id, entity_type, query, {"seed": True}, source="user", confidence=1.0)
        self.store.upsert_finding(Finding(entity))
        self.queue.put(entity_id, query, 0, priority=priority, reason="seed")
        return entity_id

    def _connectors_for(self, task):
        if task.connector and task.connector in self.connectors:
            return [self.connectors[task.connector]]
        return [connector for connector in self.connectors.values() if connector.can_handle(task.query)]

    def run(self, dry_run: bool = False) -> dict[str, int]:
        started = time.monotonic()
        processed = 0
        while len(self.queue) and processed < self.limits.max_sources:
            if time.monotonic() - started >= self.limits.max_runtime:
                break
            task = self.queue.get()
            if task is None:
                time.sleep(0.05)
                continue
            if task.depth > self.limits.max_depth:
                continue
            context = ConnectorContext(self.limits.max_requests_per_source, self.limits.confidence_threshold, dry_run)
            for connector in self._connectors_for(task):
                try:
                    for finding in connector.search(task.query, context):
                        if finding.entity.confidence < self.limits.confidence_threshold:
                            continue
                        existing = self.store.entities()
                        entity, resolved = self.resolver.canonicalize(finding.entity, existing)
                        finding.entity = entity
                        if not dry_run:
                            self.store.upsert_finding(finding)
                        processed += 1
                        for related in self._related_queries(finding):
                            self.queue.put(finding.entity.id, related, task.depth + 1, max(1, task.priority - 1), connector=connector.name, reason="entity-expansion")
                except Exception as exc:
                    self.store.audit("connector_error", {"connector": connector.name, "query": task.query, "error": str(exc)})
                    if task.attempts < self.limits.retry_count:
                        self.queue.retry(task, 2 ** task.attempts)
            self.queue.stats.completed += 1
        return {"processed": processed, "remaining": len(self.queue), "completed": self.queue.stats.completed}

    @staticmethod
    def _related_queries(finding: Finding) -> list[str]:
        values: list[str] = [finding.entity.label]
        for key, value in finding.entity.attributes.items():
            if key in {"username", "alias", "url", "website", "organization", "name"} and isinstance(value, str):
                values.append(value)
            elif key in {"usernames", "aliases", "urls"} and isinstance(value, list):
                values.extend(str(v) for v in value)
        return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))

    def refresh_due(self, after_seconds: int, limit: int) -> int:
        count = 0
        for row in self.store.sources_due(after_seconds, limit):
            self.queue.put(row["id"], row["label"], 0, priority=10, reason="scheduled-refresh")
            count += 1
        return count

    def publish(self) -> None:
        snapshot = self.store.export()
        for sink in self.sinks.values():
            sink.publish(snapshot)
