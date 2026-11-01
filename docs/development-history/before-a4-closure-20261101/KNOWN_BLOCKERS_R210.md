# Blocchi correnti verso la RC — 1 novembre 2026

**33/42 = 78,6%, PRE-RC**, perimetro autorizzato `precommercial-20261030`. Elenco coerente con `RC_EXECUTION_STRATEGY_R210.json`: 9 criteri aperti, pesi e testi invariati. Riprendere da `A5_LIFECYCLE_ACCEPTANCE_R210.md`, senza riapplicare archivi o istruzioni storici.

| Criterio | Stato | Residuo concreto |
|---|---|---|
| A4 | Implementazione/prove | Movimenti PayPal parziali e ambigui: legame univoco fra caso, capture e movimento completato. Le prove item/report supportate restano riusabili; il solo esito della disputa, un T-code o un orario di avvio non dimostrano denaro effettivamente trasferito. |
| A6 | Ambiente | Collaudo reale del ciclo Stripe e PayPal su sandbox, con credenziali e dati isolati. Le API simulate e le due prove preparate di sola lettura non certificano l'intero ciclo. |
| B6 | Ambiente | Host indipendenti per perdita worker, partizione, drain e assenza di doppia esecuzione. I processi locali e i SIGKILL restano prove locali. |
| C6 | Integrazione e target | Cambio regime concorrente e recupero crash fra host, con verifica end-to-end. Non è un residuo soltanto ambientale. |
| F4 | Implementazione/prove | Contratto indipendente di interpreti/runtime esterni e dipendenze; identità del modello effettivamente eseguito dal backend ACE. Il client o i digest scelti dal runtime non bastano. |
| F5 | Ambiente | Garanzie NC su tutti i sistemi nativi supportati; manca il collaudo installato sui rispettivi sistemi. |
| F6 | Revisione | Diritti indipendenti di ogni checkpoint opzionale effettivamente installato. Identità dei byte e policy locale non sono una concessione dei diritti upstream. |
| G5 | Ambiente | Esecuzione delle immagini e installazioni Docker/Podman/Kubernetes effettive. |
| G6 | Ambiente | Sistemi Windows/macOS installati, GPU/modelli autorizzati, VST e hardware reali. |

Non esistono pagamenti o rimborsi commerciali pre-release da importare. Le vecchie istruzioni di migrazione generale sono superate per il perimetro autorizzato. Configurazioni non equivalgono a storia monetaria; eventuali dati economici inattesi devono ancora bloccare la prima attivazione. Il cambio automatico post-checkout resta escluso dal modello RC corrente.

A5 è chiuso nel perimetro software autorizzato: 879 casi distinti passati, 61 nuovi, zero fallimenti/errori; 20 skip per browser non disponibile. Prove e matrice nel rapporto corrente. Il provider reale resta A6 e i movimenti generali irrisolti restano A4. Cronologia in `development-history/before-a5-closure-20261101/`.
