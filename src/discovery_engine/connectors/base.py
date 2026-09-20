from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable
from ..models import Finding


@dataclass(frozen=True)
class ConnectorContext:
    max_requests_per_source: int
    confidence_threshold: float
    dry_run: bool = False


class Connector(ABC):
    name = "connector"
    entity_types: set[str] = set()
    relationship_types: set[str] = set()

    @abstractmethod
    def search(self, query: str, context: ConnectorContext) -> Iterable[Finding]:
        """Return normalized findings; connector must honor source policies and limits."""

    def can_handle(self, task_query: str) -> bool:
        return True


class Sink(ABC):
    name = "sink"

    @abstractmethod
    def publish(self, snapshot: dict[str, Any]) -> None:
        """Publish a graph snapshot to an external system."""
