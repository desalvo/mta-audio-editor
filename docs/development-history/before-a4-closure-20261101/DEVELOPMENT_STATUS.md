# MTA 0.3.0-r210 — stato corrente

**Verso la RC: 33/42 = 78,6%, perimetro `precommercial-20261030`; PRE-RC, 9 criteri aperti, D/E complete (2/7). A5 chiuso.** Nessun cambiamento di testo, pesi o denominatore. Il precedente perimetro v1 resta storico e non direttamente comparabile.

Riprendere dal cumulativo **MTA-0.3.0-r210-pre-RC-a5-lifecycle-cumulative.zip**, `A5_LIFECYCLE_ACCEPTANCE_R210.md` e `validation/r210/a5-lifecycle/result.json`. Baseline Git confermata **ee4e37fd30c39a72638b303b01ca0cd5b090f272**, full CI **41156985339** verde. Il commit rimane all'utente; nessuna nuova CI remota eseguita.

Il ciclo A5 comprende quote immutabili, esiti terminali/incerti, recupero di creazioni/rimborsi e prima contabilizzazione con storico. Il residuo sulle perdite originali dell'abbonamento è ora chiuso tramite cassa autenticata completa: parziali, più capture, overlap, reintegri e rimborso dell'eccedenza della rata, senza doppio incasso o credito wallet. I delta precedenti sono tutti inclusi nel cumulativo.

**879 casi distinti passati, 61 nuovi, zero fallimenti/errori; 20 skip per browser non disponibile.** Provider simulati; SQLite/HTTP locale/concorrenza/SIGKILL/erasure effettivi. Ruff, compilazione, Bandit e inventari passano: 310 sorgenti app, 168 finding invariati, zero HIGH. Nessuna nuova accettazione browser/provider reale.

Restano **A4,A6,B6,C6,F4,F5,F6,G5,G6**; residui concreti in `KNOWN_BLOCKERS_R210.md`. A4 resta lavoro software/prove per payout/protection e movimenti ambigui; C6 conserva integrazione oltre al target. Non migrare una storia commerciale pre-release inesistente e non ricostruire i percorsi A5 ora accettati.

Commit cumulativo suggerito: `Complete payment recovery and cash-proven subscription loss repayment`.

Documenti precedenti conservati in `development-history/before-a5-closure-20261101/`. Le istruzioni storiche incompatibili col modello precommerciale sono superate.
