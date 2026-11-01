# Accettazione RC MTA 0.3.0-r210 — 1 novembre 2026

**RC: 78,6% = 33/42**, perimetro `precommercial-20261030`; **PRE-RC**, 9 criteri aperti, D/E complete (2/7). **A5 promosso a verified**, criterio e peso invariati; nessun altro criterio promosso.

La matrice completa A5 e il nuovo percorso di cassa per perdite parziali, overlap, reintegri e rata/eccedenza sono in `A5_LIFECYCLE_ACCEPTANCE_R210.md`. **879 casi distinti passati, 61 nuovi, zero fallimenti/errori; 20 skip per browser non disponibile**; i 61 nuovi casi passano tutti, incluso SIGKILL reale. API provider simulate, nessun nuovo collaudo browser/provider reale. Ruff, compilazione e gate sicurezza/inventario passano; nessuna nuova CI remota.

Evidenza corrente: `validation/r210/a5-lifecycle/result.json`. Cumulativo: `MTA-0.3.0-r210-pre-RC-a5-lifecycle-cumulative.zip`. Baseline confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`; commit all'utente.

Restano **A4,A6,B6,C6,F4,F5,F6,G5,G6**, descritti in `KNOWN_BLOCKERS_R210.md`. Payout/protection generali restano A4; il ciclo sandbox effettivo resta A6. Non riclassificare C6/F4 come soli blocchi ambientali. Il vecchio perimetro v1 resta storico, non direttamente comparabile.
