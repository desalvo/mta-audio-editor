# GPU host agent: collaudo applicativo r208

Il CT 130 ha superato il collaudo di connessione e autenticazione al socket dell’host, con UID 0.

La dashboard AI Billing interroga ora `GET /api/admin/ai-billing/gpu-host-agent/diagnostics`: report sintetico con disponibilità, autenticazione, quantità di processi e identificatori GPU. Non include token, PID host o cgroup.

Dopo la distribuzione del codice aggiornato nell’LXC, accedere come admin alla dashboard AI Billing e premere **Verifica stato**. Controllare `available: true`, `authenticated: true`, `billing_eligible: false`.

Il diagnostico non prova l'attribuzione a un job AI. Anche con telemetria disponibile, `job_attribution_verified` e `billable_gpu_time_verified` restano false; nessuna fatturazione GPU viene autorizzata.

Nessun riavvio LXC, modifica Proxmox o migrazione richiesta per questo test; può essere necessario il normale riavvio del processo applicativo per caricare i file aggiornati.
