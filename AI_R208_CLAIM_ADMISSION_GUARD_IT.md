# MTA 0.3.0-r208 — Ledger admission guard at queue claim

The worker cannot claim an authenticated, durable, opted-in Arranger/Remix job unless its inference ledger job is already present. This guards against concurrent server processes recovering a queued row during the interval between the scheduler database transaction and the ledger database transaction. When missing, the durable request is blocked for admission reconciliation and not executed. Errors reading the billing database are fail-closed. Non-billable users and older non-authenticated legacy test payloads retain backward-compatible behavior.

Tests: `PYTHONPATH=. pytest -q tests/test_r208*` (198 passed, 8 warnings). This does not establish GPU job attribution, full adapter coverage or certification on ROCm hardware.
