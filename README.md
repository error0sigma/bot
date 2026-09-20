# Public Discovery Engine

Универсальный, расширяемый движок итеративного discovery по публичным и законно доступным источникам.

## Возможности

- граф сущностей и typed relationships с `source`, `discovered_at`, `confidence`;
- очередь задач с приоритетами, глубиной, дедупликацией, retry и backoff;
- плагины-коннекторы: новые типы сущностей, полей и источников добавляются без изменения ядра;
- configurable limits: `max_depth`, `max_sources`, `max_requests_per_source`, `max_runtime`, `confidence_threshold`;
- SQLite persistence и история изменений;
- безопасный HTTP connector с allowlist, robots.txt, rate limit, timeout и размером ответа;
- фоновое обновление ранее найденных источников;
- adapter interface для Google Sheets и других sink-ов без вшивания credentials;
- dry-run и audit log.

Проект предназначен только для законного исследования публичной информации. Он не обходит авторизацию, paywall, CAPTCHA или технические ограничения источников. Перед использованием проверьте применимое законодательство, условия источников и необходимость уведомления/согласия.

## Быстрый старт

```bash
python -m discovery_engine.cli init-db discovery.db
python -m discovery_engine.cli discover discovery.db 'Ivan Ivanov' --config config.example.json
python -m discovery_engine.cli run discovery.db --config config.example.json
python -m discovery_engine.cli export discovery.db results.json
```

Для фонового режима используйте `run --watch --interval 3600`. Коннекторы регистрируются в `Engine.register_connector()`, sinks — в `Engine.register_sink()`.

## Архитектура

`Seed -> DiscoveryQueue -> Connector.search -> Findings -> EntityResolver -> GraphStore -> new queue tasks`.

Данные намеренно не ограничены фиксированным перечнем полей: `Entity.attributes` и `Finding.attributes` содержат расширяемые JSON-объекты. Коннектор сообщает `entity_types`, `relationship_types` и `capabilities`, а движок работает с общим контрактом.
