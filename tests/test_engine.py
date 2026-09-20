from discovery_engine.engine import DiscoveryEngine
from discovery_engine.models import Entity, Finding
from discovery_engine.storage import GraphStore


def test_seed_and_queue(tmp_path):
    engine = DiscoveryEngine(GraphStore(tmp_path / "test.db"))
    entity_id = engine.seed("Alice Example")
    assert entity_id
    assert len(engine.queue) == 1


def test_dynamic_attributes_are_preserved(tmp_path):
    store = GraphStore(tmp_path / "test.db")
    entity = Entity("x", "Person", "Alice", {"new_field": {"arbitrary": True}}, "test", .9)
    store.upsert_finding(Finding(entity))
    assert 'arbitrary' in store.entities()[0]["attributes"]
