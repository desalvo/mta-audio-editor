# r208 — Attribuzione diagnostica GPU end-to-end

Il modulo `app.ai_gpu_attribution_report` raccoglie snapshot `amd-smi process --json`, correla esclusivamente PID dell'host con cgroup verificati e produce un rapporto JSON deterministico. L'opzione `host_pid_namespace_verified=True` deve essere attivata soltanto da un agente sulla macchina host con accesso attendibile a `/proc` dell'host: non attivarla in un container LXC.

Il report elenca PID riconosciuti, job, memoria e contatori diagnostici grezzi, e segnala PID esterni e ambiguità. Non espone dati di autenticazione né contenuti audio. Ogni report specifica `billing_eligible: false` e `measured_gpu_seconds: null`: nessuna misura ottenuta da questo modulo è autorizzata alla fatturazione GPU.

Test: attribuzione su cgroup annidato, rifiuto in namespace non verificato, processo esterno, JSON deterministico. Mancano certificazione AMD SMI su hardware reale e una fonte attendibile di tempi GPU per processo utilizzabile per il billing.
