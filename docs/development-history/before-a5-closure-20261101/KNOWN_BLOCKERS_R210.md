# Blocchi correnti verso la RC — 1 novembre 2026

**32/42 = 76,2%, PRE-RC**, perimetro autorizzato `precommercial-20261030`. Elenco coerente con `RC_EXECUTION_STRATEGY_R210.json`: 10 criteri aperti, pesi e testi invariati. Riprendere da `PAYPAL_LOST_CREATION_HANDOFF_R210.md`, senza riapplicare archivi o istruzioni storici.

| Criterio | Stato | Residuo concreto |
|---|---|---|
| A4 | Implementazione/prove | Movimenti PayPal parziali e ambigui: legame univoco fra caso, capture e movimento completato. Le prove item/report supportate restano riusabili; il solo esito della disputa, un T-code o un orario di avvio non dimostrano denaro effettivamente trasferito. |
| A5 | Implementazione/prove | Perdite permanenti parziali dell'abbonamento e sovrapposizione con rimborsi: `original_loss_review` segnala `partial_permanent_loss_allocation_unproved` o `permanent_dispute_movement_unproved`. Occorrono prova del movimento e allocazione sulla quota/surplus originali, senza duplicare debiti. Gli esiti checkout/refund/recovery già coperti non vanno ricostruiti. |
| A6 | Ambiente | Collaudo reale del ciclo Stripe e PayPal su sandbox, con credenziali e dati isolati. Le API simulate e le due prove preparate di sola lettura non certificano l'intero ciclo. |
| B6 | Ambiente | Host indipendenti per perdita worker, partizione, drain e assenza di doppia esecuzione. I processi locali e i SIGKILL restano prove locali. |
| C6 | Integrazione e target | Cambio regime concorrente e recupero crash fra host, con verifica end-to-end. Non è un residuo soltanto ambientale. |
| F4 | Implementazione/prove | Contratto indipendente di interpreti/runtime esterni e dipendenze; identità del modello effettivamente eseguito dal backend ACE. Il client o i digest scelti dal runtime non bastano. |
| F5 | Ambiente | Garanzie NC su tutti i sistemi nativi supportati; manca il collaudo installato sui rispettivi sistemi. |
| F6 | Revisione | Diritti indipendenti di ogni checkpoint opzionale effettivamente installato. Identità dei byte e policy locale non sono una concessione dei diritti upstream. |
| G5 | Ambiente | Esecuzione delle immagini e installazioni Docker/Podman/Kubernetes effettive. |
| G6 | Ambiente | Sistemi Windows/macOS installati, GPU/modelli autorizzati, VST e hardware reali. |

Non esistono pagamenti o rimborsi commerciali pre-release da importare. Le vecchie istruzioni di migrazione generale sono superate per il perimetro autorizzato. Configurazioni non equivalgono a storia monetaria; eventuali dati economici inattesi devono ancora bloccare la prima attivazione. Il cambio automatico post-checkout resta escluso dal modello RC corrente.

Il recupero automatico della creazione PayPal persa è chiuso localmente: 723 casi distinti correnti passati, 26 nuovi, nessuno skip nelle selezioni correnti; provider simulati e nessuna nuova CI remota. La cronologia completa dei precedenti blocchi è in `development-history/before-paypal-lost-creation-20261101/KNOWN_BLOCKERS_R210.md` e nei rapporti precedenti. Non usare i numeri storici come stato corrente.
