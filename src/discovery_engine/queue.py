from __future__ import annotations

import heapq
import time
from dataclasses import dataclass

from .models import SearchTask


@dataclass
class QueueStats:
    queued: int = 0
    completed: int = 0
    failed: int = 0


class DiscoveryQueue:
    def __init__(self):
        self._heap: list[SearchTask] = []
        self._keys: set[tuple[str, str | None]] = set()
        self._sequence = 0
        self.stats = QueueStats()

    def put(self, entity_id: str, query: str, depth: int, priority: int = 0,
            connector: str | None = None, reason: str = "discovery") -> bool:
        key = (str(query).strip().casefold(), connector)
        if key in self._keys:
            return False
        self._keys.add(key)
        self._sequence += 1
        task = SearchTask(priority, self._sequence, entity_id, query, depth, connector, reason=reason)
        heapq.heappush(self._heap, task)
        self.stats.queued += 1
        return True

    def get(self) -> SearchTask | None:
        if not self._heap:
            return None
        task = heapq.heappop(self._heap)
        if task.available_at > time.time():
            heapq.heappush(self._heap, task)
            return None
        return task

    def retry(self, task: SearchTask, delay: float) -> None:
        task.attempts += 1
        task.available_at = time.time() + delay
        heapq.heappush(self._heap, task)

    def __len__(self) -> int:
        return len(self._heap)
