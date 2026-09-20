from __future__ import annotations

from pathlib import Path

import pytest

from discovery_engine.models import Entity, Finding
from discovery_engine.storage import GraphStore


def test_seed_and_queue(tmp_path):
    from discovery_engine.engine import DiscoveryEngine

    engine = DiscoveryEngine(GraphStore(tmp_path / "test.db"))
    entity_id = engine.seed("Alice Example")
    assert entity_id
    assert len(engine.queue) == 1


def test_dynamic_attributes_are_preserved(tmp_path):
    store = GraphStore(tmp_path / "test.db")
    entity = Entity("x", "Person", "Alice", {"new_field": {"arbitrary": True}}, "test", 0.9)
    store.upsert_finding(Finding(entity))
    result = store.entities()
    assert result[0]["attributes"]["new_field"]["arbitrary"] is True


def test_export_import_roundtrip(tmp_path):
    store = GraphStore(tmp_path / "graph.db")
    entity = Entity("a", "Person", "John Doe", {"username": "jdoe"}, "test", 0.8)
    store.upsert_finding(Finding(entity))
    export_path = tmp_path / "snapshot.json"
    export_path.write_text(__import__("json").dumps(store.export()), encoding="utf-8")
    imported = GraphStore(tmp_path / "imported.db")
    imported.import_snapshot(__import__("json").loads(export_path.read_text(encoding="utf-8")))
    assert imported.entities()[0]["label"] == "John Doe"
