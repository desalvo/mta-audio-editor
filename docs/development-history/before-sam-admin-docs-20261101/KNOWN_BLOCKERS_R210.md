# Blocchi correnti verso la RC — 1 novembre 2026

**34/42 = 81,0%, PRE-RC**, perimetro autorizzato `precommercial-20261030`. Elenco coerente con `RC_EXECUTION_STRATEGY_R210.json`: 8 criteri aperti, pesi e testi invariati. Riprendere da `PAYPAL_CASH_HISTORY_ACCEPTANCE_R210.md`, senza riapplicare archivi o istruzioni storici.

| Criterio | Stato | Residuo concreto |
|---|---|---|
| A6 | Ambiente | Collaudo reale del ciclo Stripe e PayPal su sandbox, con credenziali e dati isolati. Le API simulate e le due prove preparate di sola lettura non certificano l'intero ciclo. |
| B6 | Ambiente | Host indipendenti per perdita worker, partizione, drain e assenza di doppia esecuzione. I processi locali e i SIGKILL restano prove locali. |
| C6 | Integrazione e target | Cambio regime concorrente e recupero crash fra host, con verifica end-to-end. Non è un residuo soltanto ambientale. |
| F4 | Implementazione/prove | Avvio Python/guardian isolato nel checkpoint WORKER_STARTUP_ISOLATION_R210.md;  Contratto indipendente di interpreti/runtime esterni e dipendenze; identità del modello effettivamente eseguito dal backend ACE. Il client o i digest scelti dal runtime non bastano. |
| F5 | Ambiente | Garanzie NC su tutti i sistemi nativi supportati; manca il collaudo installato sui rispettivi sistemi. |
| F6 | Revisione | Diritti indipendenti di ogni checkpoint opzionale effettivamente installato. Identità dei byte e policy locale non sono una concessione dei diritti upstream. |
| G5 | Ambiente | Esecuzione delle immagini e installazioni Docker/Podman/Kubernetes effettive. |
| G6 | Ambiente | Sistemi Windows/macOS installati, GPU/modelli autorizzati, VST e hardware reali. |

Non esistono pagamenti o rimborsi commerciali pre-release da importare. Le vecchie istruzioni di migrazione generale sono superate per il perimetro autorizzato. Configurazioni non equivalgono a storia monetaria; eventuali dati economici inattesi devono ancora bloccare la prima attivazione. Il cambio automatico post-checkout resta escluso dal modello RC corrente.

A4/A5 sono chiusi nel perimetro software autorizzato: 927 casi distinti passati, 48 nuovi; zero fallimenti/errori, 20 skip browser espliciti. Prove nel rapporto corrente; sandbox reale resta A6. Cronologia in `development-history/before-a4-closure-20261101/`.

SAM Audio: la diagnostica del 1 novembre 2026 registra il fallimento di caricamento ma non la causa originale. Una regressione dell’avvio isolato successiva è stata corretta; attendere journal o nuova prova reale classificata. Vedi `SAM_MODEL_LOAD_DIAGNOSTICS_R210.md`.
