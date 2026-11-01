# MTA 0.3.0-r210 — stato corrente

**Verso la RC: 34/42 = 81,0%, PRE-RC**, perimetro `precommercial-20261030`; 8 criteri aperti, D/E complete (2/7). **A4 e A5 chiusi**; in questo checkpoint è promosso soltanto A4, con testo e peso invariati.

Riprendere da `MTA-0.3.0-r210-pre-RC-paypal-cash-history-cumulative.zip`, `PAYPAL_CASH_HISTORY_ACCEPTANCE_R210.md` e `validation/r210/paypal-cash-history/result.json`. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, full CI `41156985339` verde; commit all'utente e nessuna nuova CI remota.

Completata la riconciliazione finanziaria dei payout PayPal finali sulla cassa originale completa: primo accredito netto, più capture senza ripartizioni stimate, più casi, rimborsi, reintegri, rata e rimborso operatore incerto. Le prove mancanti/instabili e i casi non finali restano bloccati. Quote e ledger A5 conservati; nessuna migrazione di storia pre-release inesistente.

**927 casi distinti passati, 48 nuovi; zero fallimenti/errori, 20 skip browser espliciti.** Provider simulati; HTTP locale, DB, concorrenza, SIGKILL ed erasure reali e isolati. Ruff, compilazione e gate sicurezza/inventario passano; 168 finding invariati, zero HIGH. Nessuna nuova accettazione browser/provider reale.

Restano **A6,B6,C6,F4,F5,F6,G5,G6**. A6 è bloccato dai prerequisiti riportati in `A6_SANDBOX_PREREQUISITES_R210.md`. C6 mantiene anche integrazione software. F4 richiede identità indipendente di runtime/dipendenze/backend ACE; F6 diritti dei checkpoint effettivi. Non trasformare questi residui in semplici skip o riaprire A4/A5. Dettagli in `KNOWN_BLOCKERS_R210.md`.

Commit cumulativo suggerito: `Complete canonical payment recovery and cash-proven payout reconciliation`.

Documenti precedenti conservati in `development-history/before-a4-closure-20261101/`.
