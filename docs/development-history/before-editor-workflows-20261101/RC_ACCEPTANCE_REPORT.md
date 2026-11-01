# Stato aggiornato — documentazione SAM 2026-11-01

RC **34/42 = 81,0%, PRE-RC**; nessun criterio promosso. Il journal originale ha chiarito il 401 gated Hugging Face; accesso e successiva inferenza sono ancora da verificare sul sistema reale. Procedura in `SAM_AUDIO_ADMIN_GUIDE_R210.md` e nei manuali amministratore IT/EN.

# Stato aggiornato — diagnostica SAM 2026-11-01

RC **34/42 = 81,0%, PRE-RC**; nessun criterio promosso. Il checkpoint `SAM_MODEL_LOAD_DIAGNOSTICS_R210.md` corregge una regressione d'avvio e migliora la diagnosi, ma il fallimento originario non è ancora spiegato o verificato sul target.

# Stato aggiornato — worker startup 2026-11-01

RC **34/42 = 81,0%, PRE-RC**; nessun criterio promosso. Isolamento di avvio e limiti in `WORKER_STARTUP_ISOLATION_R210.md`, prove in `validation/r210/worker-startup-isolation/result.json`. F4 resta aperto. Archivio di ripresa `MTA-0.3.0-r210-pre-RC-worker-startup-isolation-cumulative.zip`.

# Accettazione RC MTA 0.3.0-r210 — 1 novembre 2026

**RC: 81,0% = 34/42**, perimetro `precommercial-20261030`; **PRE-RC**, 8 criteri aperti e D/E complete (2/7). A4 promosso a verified, A5 resta verified. Nessun testo, peso o denominatore cambiato.

Matrice A4, comportamento e limiti in `PAYPAL_CASH_HISTORY_ACCEPTANCE_R210.md`. **927 casi distinti passati, 48 nuovi; zero fallimenti/errori, 20 skip browser espliciti**. I 48 nuovi casi passano, incluso SIGKILL. API provider simulate; nessun nuovo collaudo browser/provider. Ruff, compilazione e quattro gate passano; nessuna nuova CI remota.

Cumulativo `MTA-0.3.0-r210-pre-RC-paypal-cash-history-cumulative.zip`; evidenza `validation/r210/paypal-cash-history/result.json`. Baseline confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, commit differito.

Restano **A6,B6,C6,F4,F5,F6,G5,G6**. Prerequisiti A6 nel rapporto dedicato; C6 conserva lavoro di integrazione e F4/F6 contratti e revisioni indipendenti. Il vecchio perimetro v1 resta storico e non direttamente comparabile.
