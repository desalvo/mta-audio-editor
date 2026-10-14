# R208 Native/server durable request discovery

- Endpoint GET /api/native/ai-workers/remote-history/{kind}: native-only, per-kind current HTTPS remote configuration, bearer token stays server-side, validated paginated remote request discovery.
- Native modal can query configured remote workers and display persisted request states after a desktop restart without triggering inference.
- Discovered server requests are intentionally kept separate from local journal receipts; no unverified import or replay.
- Unit/integration targeted tests: 16 passed. The broad r208 regression timed out and is not certified.
- Hardware GPU, actual remote server, Windows/macOS native runtime tests remain pending.
