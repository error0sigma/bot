from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from .engine import DiscoveryEngine, Limits
from .storage import GraphStore
from .connectors.http import PublicHttpConnector


def load_engine(db: str, config_path: str | None) -> DiscoveryEngine:
    config = json.loads(Path(config_path).read_text()) if config_path else {}
    engine = DiscoveryEngine(GraphStore(db), Limits.from_dict(config.get("limits", {})))
    http = config.get("http", {})
    engine.register_connector(PublicHttpConnector(
        http.get("allowed_domains", []), http.get("user_agent", "public-discovery-engine/0.1"),
        http.get("requests_per_minute", 30), http.get("respect_robots_txt", True),
        http.get("max_response_bytes", 2_000_000)))
    return engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Lawful public-source discovery engine")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-db"); init.add_argument("db")
    discover = sub.add_parser("discover"); discover.add_argument("db"); discover.add_argument("query"); discover.add_argument("--config")
    run = sub.add_parser("run"); run.add_argument("db"); run.add_argument("--config"); run.add_argument("--watch", action="store_true"); run.add_argument("--interval", type=int, default=3600)
    export = sub.add_parser("export"); export.add_argument("db"); export.add_argument("output")
    args = parser.parse_args()
    if args.command == "init-db":
        GraphStore(args.db).close(); return
    if args.command == "export":
        store = GraphStore(args.db); Path(args.output).write_text(json.dumps(store.export(), ensure_ascii=False, indent=2)); store.close(); return
    engine = load_engine(args.db, args.config)
    if args.command == "discover":
        print(engine.seed(args.query)); print(engine.run())
    else:
        while True:
            cfg = json.loads(Path(args.config).read_text()) if args.config else {}
            bg = cfg.get("background", {})
            engine.refresh_due(bg.get("refresh_after_seconds", 86400), bg.get("max_items_per_cycle", 100))
            print(engine.run())
            if not args.watch: break
            time.sleep(args.interval)
    engine.store.close()
