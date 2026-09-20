from __future__ import annotations

from pathlib import Path

from discovery_engine.engine import DiscoveryEngine, Limits
from discovery_engine.models import Entity, Finding
from discovery_engine.storage import GraphStore


def test_engine_registers_seed_and_runs(tmp_path):
    engine = DiscoveryEngine(GraphStore(tmp_path / "discovery.db"), Limits(max_depth=1, max_sources=5))
    entity_id = engine.seed("Ivan Ivanov")
    assert entity_id
    assert len(engine.queue) == 1
    stats = engine.run(dry_run=True)
    assert "processed" in stats


def test_graph_store_export_roundtrip(tmp_path):
    path = tmp_path / "graph.db"
    store = GraphStore(path)
    entity = Entity("p1", "Person", "Ivan Ivanov", {"username": "ivan_ivanov"}, "test", 0.9)
    store.upsert_finding(Finding(entity))
    exported = store.export()
    assert exported["schema_version"] == 1
    assert exported["entities"][0]["label"] == "Ivan Ivanov"
