from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SourceRateLimiter:
    limit_per_minute: int = 30
    buckets: dict[str, list[float]] = field(default_factory=dict)

    def acquire(self, source: str) -> bool:
        now = time.time()
        bucket = self.buckets.setdefault(source, [])
        bucket[:] = [ts for ts in bucket if now - ts < 60]
        if len(bucket) >= self.limit_per_minute:
            return False
        bucket.append(now)
        return True


@dataclass
class PriorityController:
    base_weight: float = 1.0

    def score(self, task_priority: int, depth: int, source: str | None = None) -> float:
        score = self.base_weight + task_priority + max(0, 5 - depth)
        if source in {"github", "search_api", "rss"}:
            score += 1.5
        return score


class BackgroundScheduler:
    def __init__(self, engine, config: dict | None = None, rate_limiter: SourceRateLimiter | None = None):
        self.engine = engine
        self.config = config or {}
        self.rate_limiter = rate_limiter or SourceRateLimiter(limit_per_minute=self.config.get("requests_per_minute", 30))
        self.priority_controller = PriorityController()

    def run_once(self) -> dict:
        refresh_after = self.config.get("refresh_after_seconds", 86400)
        max_items = self.config.get("max_items_per_cycle", 100)
        self.engine.refresh_due(refresh_after, max_items)
        stats = self.engine.run()
        return {"scheduler": "tick", **stats}

    def run_forever(self, interval: int = 3600) -> None:
        while True:
            self.run_once()
            time.sleep(interval)
