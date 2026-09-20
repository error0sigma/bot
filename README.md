# Public Discovery Engine

Universal public-source discovery engine with plugin architecture.

## Features

- entity graph with typed relationships, source, confidence and audit trail
- discovery queue with priority, deduplication and retry
- configurable runtime limits
- entity resolution and deduplication
- GitHub, RSS, search API, and HTTP connectors
- Google Sheets sink and background scheduler
- SQLite persistence with schema versioning
- CLI for seed, run, export and import

## Quick start

```bash
pip install -e .
discovery init-db discovery.db
discovery discover discovery.db "Ivan Ivanov" --config config.example.json
discovery export discovery.db results.json
```

## Config example

```json
{
  "limits": {"max_depth": 2, "max_sources": 50, "max_runtime": 300, "confidence_threshold": 0.55},
  "http": {"enabled": true, "allowed_domains": ["api.github.com", "github.com"], "requests_per_minute": 30},
  "connectors": {"github": {"enabled": true}, "rss": {"enabled": false}, "search_api": {"enabled": false}},
  "sheets": {"enabled": false, "webhook_url": "https://example.com/webhook"},
  "background": {"refresh_after_seconds": 86400, "max_items_per_cycle": 100}
}
```

## Notes

This project is designed for lawful public-source discovery only. It respects allowlists, HTTP limits, and does not bypass auth barriers, paywalls, or robots exclusions.
