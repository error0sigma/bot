from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .engine import DiscoveryEngine, Limits
from .storage import GraphStore


def _export_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lawful public-source discovery engine")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-db", help="Create a new SQLite database")
    init.add_argument("db")

    discover = sub.add_parser("discover", help="Seed a discovery query")
    discover.add_argument("db")
    discover.add_argument("query")
    discover.add_argument("--config")

    run = sub.add_parser("run", help="Run queued discovery")
    run.add_argument("db")
    run.add_argument("--config")
    run.add_argument("--watch", action="store_true")
    run.add_argument("--interval", type=int, default=3600)

    export = sub.add_parser("export", help="Export graph to JSON")
    export.add_argument("db")
    export.add_argument("output")

    imp = sub.add_parser("import", help="Import a graph snapshot")
    imp.add_argument("db")
    imp.add_argument("input")

    list_cmd = sub.add_parser("list", help="List entities")
    list_cmd.add_argument("db")

    args = parser.parse_args()

    if args.command == "init-db":
        GraphStore(args.db).close()
        return

    if args.command == "export":
        store = GraphStore(args.db)
        _export_json(args.output, store.export())
        store.close()
        return

    if args.command == "import":
        store = GraphStore(args.db)
        with open(args.input, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        count = store.import_snapshot(payload)
        store.close()
        print(json.dumps({"imported_entities": count}, ensure_ascii=False))
        return

    if args.command == "list":
        store = GraphStore(args.db)
        print(json.dumps(store.entities(), ensure_ascii=False, indent=2))
        store.close()
        return

    engine = None
    if args.command in {"discover", "run"}:
        config = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
        engine = DiscoveryEngine(GraphStore(args.db), Limits.from_dict(config.get("limits", {})))
        http_cfg = config.get("http", {})
        if http_cfg.get("enabled", True):
            from .connectors import GitHubConnector, NameVariantConnector, PublicHttpConnector, RSSConnector, SearchAPIConnector, GoogleSheetsSink
            engine.register_connector(PublicHttpConnector(
                http_cfg.get("allowed_domains", []),
                http_cfg.get("user_agent", "public-discovery-engine/0.2"),
                http_cfg.get("requests_per_minute", 30),
                http_cfg.get("respect_robots_txt", True),
                http_cfg.get("max_response_bytes", 2_000_000),
            ))
        engine.register_connector(NameVariantConnector())
        connectors_cfg = config.get("connectors", {})
        if connectors_cfg.get("github", {}).get("enabled", False):
            engine.register_connector(GitHubConnector())
        if connectors_cfg.get("rss", {}).get("enabled", False):
            engine.register_connector(RSSConnector(connectors_cfg.get("rss", {}).get("feeds", [])))
        if connectors_cfg.get("search_api", {}).get("enabled", False):
            engine.register_connector(SearchAPIConnector())
        sheets_cfg = config.get("sheets", {})
        if sheets_cfg.get("enabled", False):
            engine.register_sink(GoogleSheetsSink(sheets_cfg.get("webhook_url"), sheets_cfg.get("path")))

    if args.command == "discover":
        entity_id = engine.seed(args.query)
        print(json.dumps({"entity_id": entity_id, "result": engine.run()}, ensure_ascii=False))
        engine.store.close()
        return

    while True:
        config = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
        bg = config.get("background", {})
        engine.refresh_due(bg.get("refresh_after_seconds", 86400), bg.get("max_items_per_cycle", 100))
        print(json.dumps(engine.run(), ensure_ascii=False))
        if not args.watch:
            break
        time.sleep(args.interval)
    engine.store.close()
