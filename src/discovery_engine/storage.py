from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable
from .models import Entity, Relationship, Finding, dumps, utc_now


class GraphStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS entities (
          id TEXT PRIMARY KEY, type TEXT NOT NULL, label TEXT NOT NULL,
          attributes TEXT NOT NULL, source TEXT, confidence REAL NOT NULL,
          discovered_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS relationships (
          id TEXT PRIMARY KEY, source_entity_id TEXT NOT NULL, target_entity_id TEXT NOT NULL,
          relationship_type TEXT NOT NULL, source TEXT, confidence REAL NOT NULL,
          discovered_at TEXT NOT NULL, attributes TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS findings (
          id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT NOT NULL,
          source_url TEXT, attributes TEXT NOT NULL, discovered_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
          payload TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_entities_seen ON entities(last_seen_at);
        CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity_id);
        ''')
        self.db.commit()

    def upsert_finding(self, finding: Finding) -> None:
        e = finding.entity
        old = self.db.execute("SELECT confidence FROM entities WHERE id=?", (e.id,)).fetchone()
        confidence = max(float(old[0]) if old else 0.0, e.confidence)
        self.db.execute('''INSERT INTO entities VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET label=excluded.label, attributes=excluded.attributes,
          source=excluded.source, confidence=?, last_seen_at=?''',
          (e.id, e.type, e.label, dumps(e.attributes), e.source, confidence,
           e.discovered_at, e.last_seen_at, confidence, utc_now()))
        for r in finding.relationships:
            self.db.execute('''INSERT OR IGNORE INTO relationships VALUES(?,?,?,?,?,?,?,?)''',
              (r.id, r.source_entity_id, r.target_entity_id, r.relationship_type,
               r.source, r.confidence, r.discovered_at, dumps(r.attributes)))
        self.db.execute("INSERT INTO findings(entity_id,source_url,attributes,discovered_at) VALUES(?,?,?,?)",
                        (e.id, finding.source_url, dumps(finding.attributes), utc_now()))
        self.audit("finding_upserted", {"entity_id": e.id, "source": e.source})
        self.db.commit()

    def audit(self, event: str, payload: dict) -> None:
        self.db.execute("INSERT INTO audit_log(event,payload,created_at) VALUES(?,?,?)",
                         (event, dumps(payload), utc_now()))

    def entities(self) -> list[dict]:
        return [dict(x) for x in self.db.execute("SELECT * FROM entities ORDER BY discovered_at")]

    def relationships(self) -> list[dict]:
        return [dict(x) for x in self.db.execute("SELECT * FROM relationships ORDER BY discovered_at")]

    def sources_due(self, after_seconds: int, limit: int) -> list[dict]:
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=after_seconds)).isoformat()
        return [dict(x) for x in self.db.execute(
            "SELECT * FROM entities WHERE last_seen_at < ? ORDER BY last_seen_at LIMIT ?", (cutoff, limit))]

    def export(self) -> dict:
        return {"entities": self.entities(), "relationships": self.relationships()}

    def close(self) -> None:
        self.db.close()
