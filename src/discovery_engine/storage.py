from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try: return json.loads(value)
        except json.JSONDecodeError: return value
    return value


class GraphStore:
    def __init__(self, path: str | Path):
        import sqlite3
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY,type TEXT NOT NULL,label TEXT NOT NULL,attributes TEXT NOT NULL,source TEXT,confidence REAL NOT NULL,discovered_at TEXT NOT NULL,last_seen_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS relationships (id TEXT PRIMARY KEY,source_entity_id TEXT NOT NULL,target_entity_id TEXT NOT NULL,relationship_type TEXT NOT NULL,source TEXT,confidence REAL NOT NULL,discovered_at TEXT NOT NULL,attributes TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS findings (id INTEGER PRIMARY KEY AUTOINCREMENT,entity_id TEXT NOT NULL,source_url TEXT,attributes TEXT NOT NULL,discovered_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_entities_seen ON entities(last_seen_at);
        CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity_id);
        ''')
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
        self.db.commit()

    def upsert_finding(self, finding: "Finding") -> None:
        from .models import dumps, utc_now
        e = finding.entity
        old = self.db.execute("SELECT confidence FROM entities WHERE id=?", (e.id,)).fetchone()
        confidence = max(float(old[0]) if old else 0, e.confidence)
        self.db.execute('''INSERT INTO entities VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET label=excluded.label,attributes=excluded.attributes,source=excluded.source,confidence=?,last_seen_at=?''', (e.id,e.type,e.label,dumps(e.attributes),e.source,confidence,e.discovered_at,e.last_seen_at,confidence,utc_now()))
        for r in finding.relationships:
            self.db.execute("INSERT OR IGNORE INTO relationships VALUES(?,?,?,?,?,?,?,?)", (r.id,r.source_entity_id,r.target_entity_id,r.relationship_type,r.source,r.confidence,r.discovered_at,dumps(r.attributes)))
        self.db.execute("INSERT INTO findings(entity_id,source_url,attributes,discovered_at) VALUES(?,?,?,?)", (e.id,finding.source_url,dumps(finding.attributes),utc_now()))
        self.audit("finding_upserted", {"entity_id":e.id,"source":e.source})
        self.db.commit()

    def audit(self, event: str, payload: dict[str, Any]) -> None:
        from .models import dumps, utc_now
        self.db.execute("INSERT INTO audit_log(event,payload,created_at) VALUES(?,?,?)", (event,dumps(payload),utc_now()))
        self.db.commit()

    def _rows(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        rows = [dict(x) for x in self.db.execute(sql, args).fetchall()]
        for row in rows:
            if "attributes" in row: row["attributes"] = _json(row["attributes"])
        return rows

    def entities(self) -> list[dict[str, Any]]: return self._rows("SELECT * FROM entities ORDER BY discovered_at")
    def relationships(self) -> list[dict[str, Any]]: return self._rows("SELECT * FROM relationships ORDER BY discovered_at")
    def sources_due(self, seconds: int, limit: int) -> list[dict[str, Any]]:
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
        return self._rows("SELECT * FROM entities WHERE last_seen_at < ? ORDER BY last_seen_at LIMIT ?", (cutoff, limit))
    def export(self) -> dict[str, Any]: return {"schema_version": SCHEMA_VERSION, "entities": self.entities(), "relationships": self.relationships()}

    def import_snapshot(self, snapshot: dict[str, Any]) -> int:
        if int(snapshot.get("schema_version", 0)) > SCHEMA_VERSION: raise ValueError("unsupported schema version")
        from .models import Entity, Relationship, Finding
        count = 0
        for raw in snapshot.get("entities", []):
            self.upsert_finding(Finding(Entity(raw["id"],raw["type"],raw["label"],raw.get("attributes",{}),raw.get("source",""),float(raw.get("confidence",.5)),raw.get("discovered_at"),raw.get("last_seen_at"))))
            count += 1
        for raw in snapshot.get("relationships", []):
            self.db.execute("INSERT OR IGNORE INTO relationships VALUES(?,?,?,?,?,?,?,?)", (raw["id"],raw["source_entity_id"],raw["target_entity_id"],raw["relationship_type"],raw.get("source",""),raw.get("confidence",.5),raw.get("discovered_at",""),json.dumps(raw.get("attributes",{}))))
        self.db.commit()
        return count

    def close(self) -> None: self.db.close()
