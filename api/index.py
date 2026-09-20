from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery_engine.connectors import (  # noqa: E402
    GitHubConnector,
    NameVariantConnector,
    SearchAPIConnector,
)
from discovery_engine.engine import DiscoveryEngine, Limits  # noqa: E402
from discovery_engine.storage import GraphStore  # noqa: E402

app = Flask(__name__)


def _authorized() -> bool:
    expected = os.getenv("CRON_SECRET")
    if not expected:
        return True
    supplied = request.headers.get("Authorization", "")
    return supplied == f"Bearer {expected}" or request.headers.get("x-cron-secret") == expected


def _config() -> dict:
    return {
        "limits": {
            "max_depth": int(os.getenv("DISCOVERY_MAX_DEPTH", "1")),
            "max_sources": int(os.getenv("DISCOVERY_MAX_SOURCES", "20")),
            "max_runtime": int(os.getenv("DISCOVERY_MAX_RUNTIME", "20")),
            "confidence_threshold": float(os.getenv("DISCOVERY_CONFIDENCE", "0.55")),
            "retry_count": int(os.getenv("DISCOVERY_RETRY_COUNT", "2")),
        },
        "github": os.getenv("ENABLE_GITHUB", "1") == "1",
        "search": bool(os.getenv("SEARCH_API_URL")),
    }


def _engine() -> tuple[DiscoveryEngine, GraphStore]:
    # Vercel's filesystem is ephemeral. Use /tmp only for this request.
    db = Path(tempfile.mkdtemp(prefix="discovery-")) / "request.db"
    config = _config()
    store = GraphStore(db)
    engine = DiscoveryEngine(store, Limits.from_dict(config["limits"]))
    engine.register_connector(NameVariantConnector())
    if config["github"]:
        engine.register_connector(GitHubConnector())
    if config["search"]:
        engine.register_connector(SearchAPIConnector())
    return engine, store


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "public-discovery-engine"})


@app.route("/api/discover", methods=["GET", "POST"])
def discover():
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    query = (request.args.get("query") or payload.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    engine, store = _engine()
    try:
        entity_id = engine.seed(query)
        result = engine.run()
        snapshot = store.export()
        if os.getenv("DISCOVERY_SHEETS_WEBHOOK_URL"):
            from discovery_engine.connectors.sheets import GoogleSheetsSink
            GoogleSheetsSink(webhook_url=os.environ["DISCOVERY_SHEETS_WEBHOOK_URL"]).publish(snapshot)
        return jsonify({"entity_id": entity_id, "result": result, "snapshot": snapshot})
    finally:
        store.close()


@app.get("/api/cron")
def cron():
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    query = os.getenv("DISCOVERY_QUERY", "").strip()
    if not query:
        return jsonify({"ok": True, "skipped": True, "reason": "DISCOVERY_QUERY is not configured"})
    with app.test_request_context(f"/api/discover?query={query}"):
        return discover()


# Vercel detects this Flask WSGI application as the Python function entrypoint.
