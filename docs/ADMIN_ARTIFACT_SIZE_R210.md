# r210 — administrator-configurable AI artifact size

In **Settings > AI Queue**, an administrator can edit **Dimensione massima
artefatti per job (MiB)**. Default: **1024 MiB**. Accepted range: **64–8192 MiB**.
The value is the sum of uncompressed output files for one worker invocation,
not a stem count. The maximum number of artifacts remains 16. Source audio
retains its separate 512 MiB limit.

GET/PUT `/api/admin/ai-execution/settings` exposes `max_artifact_mib` alongside
the existing concurrency setting. Both endpoints require an administrator.
Partial updates preserve the omitted setting; combined updates validate all
fields before one transaction. The policy is persisted in the queue SQLite DB
and survives service restarts. Only integer MiB values in range are accepted.

The server snapshots the policy at worker execution start, injects it through
an operator-controlled environment variable, and supplies the same budget to
the packaging consumer. Request-plan fields cannot replace it. Changing the
setting affects later executions; a running job keeps its original budget.
ZIP/manifest overhead has a separate 2 MiB allowance. Web/native delivery and
replay caches accept results up to the absolute 8 GiB + 2 MiB transport ceiling,
so a completed result survives a later reduction of the admin setting.

The HTTP reader uses at most 1 MiB read requests, avoiding a ceiling-sized
allocation for a small response without Content-Length. The current result API
still holds complete byte payloads in memory: configure large budgets according
to available memory, concurrency and temporary/cache storage. Increasing this
setting does not increase a model's supported duration or the number of stems
it can produce. Updated native clients are needed to consume results larger
than the limits in their previously installed build.

No AI-model environment reinstall is required. GPU evidence requirements,
authentication, checksums, private-file guards and accounting remain unchanged.
No production deployment or real GPU inference was performed in this cycle.
Revision remains 0.3.0-r210.
