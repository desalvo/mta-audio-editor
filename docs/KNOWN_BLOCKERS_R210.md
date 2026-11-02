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

SAM Audio: il journal originale del 1 novembre 2026 ha identificato `GatedRepoError` HTTP 401 sui modelli Base e Large. Autenticazione/autorizzazione, login e nuova prova sul server restano da verificare. I manuali amministratore IT/EN documentano la configurazione osservata; vedi `SAM_AUDIO_ADMIN_GUIDE_R210.md`.

Richieste editing: matching automatico beat e fase implementato; stime musicali su brani reali e zoom nativo richiedono prove sui rispettivi target. Vedi `BEAT_SYNC_R210.md`.

Merish5 / Xynthia2: i due export completi sintetici MTA8 e MTA16 ora riproducono tutte le tracce e mostrano testo e accordi sincronizzati sul Merish5+ dell’utente. Le prove sintetiche di evidenziazione per parole e lettere sono positive sullo stesso Merish; anche tre export granulari completi dell’app sono stati provati con successo; l’uso dei tempi delle sillabe e progetti ulteriori attendono verifica hardware. TKEY è visualizzato sul Merish; rimangono aperti il significato di BaseKey e il funzionamento della trasposizione. Su Merish5+ le prove T2 con preconteggio azzerato hanno marker selezionabili ai tempi corretti ed evidenziazione completa sia MTA8 sia MTA16; gli export completi dell’app con testo sono confermati e i marker senza testo sono visibili e selezionabili. Anche le prove senza testo con toni ripetuti fino alla fine funzionano sul Merish5+ dell’utente. Nelle prove con marker e testo a righe il testo avanza, ma non sono ancora confermati i marker di quegli stessi file. Su esplicita richiesta l’export con marker è consentito anche per metronomi a zone/adattivi, trattati come audio; la mappa dinamica non è trasferita. Nelle prove di tempo MIDI variabile i marker funzionano, ma i cambi BPM non sono visibili: la visualizzazione e la sincronizzazione musicale dinamica restano da verificare, oltre a Xynthia2. Vedi `MERISH5_MTA16_EXPERIMENTAL_IT.md`.

Avvio senza marker: il confronto MTA16 A/B conferma sul Merish5+ che `PreCntUSec=2000000` salta l'inizio, mentre `0` parte dall'inizio. L'export ora usa zero anche senza marker. Gli export sintetici reali dell'app MTA8 e MTA16, con e senza lyrics/chords, sono stati confermati dall'utente: partenza da 0, audio per 12 s e accordi corretti. L'ultima riga evidenziata tornava bianca a circa 10 s; nelle quattro prove successive con terminatore COLORS posticipato rimane evidenziata fino al termine. Il writer usa ora la variante A, che sposta solo il terminatore. L'utente conferma anche le quattro prove con marker a 2/5/8 s, MTA8 e MTA16 con e senza lyrics. L'export del progetto reale Cherish dopo la rimozione della compensazione, durate più lunghe e Xynthia2 attendono conferma hardware.
