# Accettazione RC MTA 0.3.0-r210 — 1 novembre 2026

**RC: 76,2% = 32/42**, perimetro `precommercial-20261030`; **PRE-RC**, 10 criteri aperti, D/E complete (2/7). Nessun criterio promosso in questo checkpoint. Il vecchio perimetro resta 29/42 = 69,0%, non direttamente comparabile. Le revisioni autorizzate di C3/C5/D6 restano documentate in `PRECOMMERCIAL_MODEL_R210.md`.

L'ultimo percorso completato è il recupero del riferimento PayPal dopo perdita della risposta di creazione, attraverso webhook verificato e riconciliazione canonica, fino a saldo e rata corretti. Prova locale: **723 test distinti passati, 26 nuovi, zero fallimenti/errori/skip nelle selezioni correnti**; comprende SIGKILL effettivo e provider simulati. Ruff, compilazione, SAST e inventari passano. Nessuna nuova CI, prova browser o accettazione provider/host/OS/hardware reale. I precedenti skip browser restano non accettati.

Evidenza corrente: `PAYPAL_LOST_CREATION_HANDOFF_R210.md`, `validation/r210/paypal-lost-creation/result.json`. Cumulativo: `MTA-0.3.0-r210-pre-RC-paypal-lost-creation-cumulative.zip`. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`; delta non dichiarati committati.

Restano **A4,A5,A6,B6,C6,F4,F5,F6,G5,G6**, con residui concreti in `KNOWN_BLOCKERS_R210.md`. In particolare A5 non viene promosso: la prova e l'allocazione generale delle perdite permanenti parziali restano da completare. Nessuna semplificazione ulteriore del criterio, nessun ricalcolo dei pesi e nessuna riclassificazione dei residui software come soli problemi ambientali.
