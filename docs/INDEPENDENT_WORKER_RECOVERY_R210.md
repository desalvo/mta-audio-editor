# B2 chiuso — recupero indipendente dei worker Linux

30 ottobre 2026 · MTA 0.3.0-r210 · PRE-RC.

**Avanzamento reale dei criteri RC originali: 28/42 → 29/42, 66,7% → 69,0%.** Il criterio **B2, “Actual supervisor-crash recovery with external worker quiescence proof”**, è verificato con un nuovo percorso di produzione e prove effettive del kernel Linux. Testo, peso e denominatore dei 42 criteri non cambiano. E resta l'unica macroarea interamente accettata; B6 impedisce ancora la chiusura dell'intera B. La RC e la transizione finanziaria globale restano bloccate.

## Baseline e input

Ultimo commit dichiarato: `4014a1fd5bfccc4e7f65c32345cb4c52f98f3d8d`. La CI standard 40972934180 riuscita e la precedente full CI restano prove storiche dei rispettivi commit, non una nuova esecuzione di questo delta. Nessun nuovo commit è stato dichiarato dopo la consegna adapter-identity.

Input del ciclo: `MTA-0.3.0-r210-pre-RC-adapter-identity-cumulative.zip`, 100.152.932 byte, SHA-256 `65f119b2c4194ecd84b7e582bfa9a98bd856eb251077638e0402b8c47bd2bf9c`, 4939 percorsi e 694 file `.log`. Il cumulativo conserva tutti questi percorsi, i byte dei log, i modi e i metadati ZIP originali; contiene anche tutto il delta restored-rights precedente. Il nuovo manifest di preservazione distingue file originali invariati, modifiche e aggiunte.

## Il cambiamento funzionale

Il solo supervisore precedente poteva terminare senza raccogliere i discendenti del worker, specialmente dopo `setsid` o un'uscita anticipata del padre. La sola osservazione di `/proc` non provava un albero vuoto. Senza delega cgroup mancava inoltre la prova kernel reale del recupero dopo un suo SIGKILL.

Il percorso Linux senza cgroup configurato ora avvia **un processo di controllo indipendente per ciascun albero di lavoro**. Quel processo abilita e verifica `PR_SET_CHILD_SUBREAPER` soltanto su sé stesso; il server web non cambia stato globale e non esegue `wait(-1)` sui figli di altre richieste. Il modello non parte prima della registrazione del suo scope originale, legato a job, account, claim/token hash, host/boot/namespace e identità di creazione di supervisore e processo di controllo.

La chiusura della pipe del supervisore, anche per SIGKILL, attiva la pulizia. I processi orfani vengono adottati dal subreaper, anche se hanno cambiato sessione. I segnali usano pidfd, con rilettura della parentela dopo l'apertura; un numero PID riciclato non redirige il segnale. La profondità `NSpid` gestisce il procfs di una namespace antenata. Il processo continua a raccogliere i figli finché **il kernel restituisce ECHILD**. Un elenco `/proc` vuoto, un timeout o la morte presunta di un PID non costituiscono una ricevuta.

Le chiamate di produzione del registro server, Arranger/Remix differiti, preparazione FFmpeg, Studio locale Linux, compatibilità nativa e worker pull usano il runner condiviso. Un cgroup esplicitamente configurato conserva il proprio percorso, senza fallback che nasconda una delega guasta. Fuori da Linux restano i limiti nativi precedenti, separati da F5/G6.

Nel completamento normale, `wait4` misura la CPU dell'albero raccolto: include anche i figli brevi già attesi dai loro padri e gli orfani attesi dal processo di controllo, senza sommare contatori host. Il processo di controllo non addebita la propria CPU. Non si inventano GPU o I/O fisico. Un albero noto, come il vero FFmpeg del backing DSP, può quindi completare anche senza cgroup delegato, dopo la prova kernel.

## Recupero economico e confini

La ricevuta immutabile entra nel journal di scope già esistente e nel contatore originale `worker_scope_count`; non nasce una seconda identità del job. **La ricevuta fisica non pubblica output, non fattura, non chiude il claim e non riesegue inferenza.** Dopo la perdita del supervisore, l'operatore usa le API private esistenti di anteprima e risoluzione. Se non esiste una misura o pubblicazione già congelata, può assumere esplicitamente la perdita sconosciuta: charge cliente zero, uso ancora sconosciuto `{}`, riserve originali liberate e stesso claim/fence chiusi. Rimangono obbligatori i controlli di prove già presenti, epoch, conferme, audit, replay e non riallocazione NC.

Se muore anche il processo indipendente, manca una ricevuta o l'arresto non è verificabile, il job resta sospeso. Non si crea un sostituto e non si libera il lavoro per scadenza. Il supervisore originale o un amministratore non possono impersonare il processo indipendente per dichiarare fermo l'albero. Le nuove continuazioni DB di bootstrap/cleanup sono ristrette allo scope originale, all'identità del processo e al claim già ammesso; non costituiscono una nuova ammissione finanziaria durante drain.

**ACE-Step è un caso distinto:** un client HTTP locale può terminare mentre il servizio esterno continua. Il solo albero locale non ne prova la quiescenza. Gli scope ACE/Arranger/Remix non acquisiscono la facoltà di chiudere una perdita esterna con questa ricevuta, e la risoluzione rifiuta tali job anche se il solo client è fermo. Il normale completamento supportato conserva i controlli precedenti. La quiescenza di host remoti non osservabili non viene dedotta da questa prova locale; B6 rimane aperto.

## Accettazione effettiva

**628 casi correnti distinti passati, 16 nuovi, zero failure/error/skip correnti nella selezione.** Il rapporto `docs/validation/r210/independent-guardian-result.json` conserva identità JUnit, ordine degli ultimi esiti, hash dei rapporti, riuso e prove iniziali corrette. Non sommare le riesecuzioni né i 905 casi del ciclo precedente.

Le prove nuove non sostituiscono il kernel con file sintetici:

- Worker, figlio e nipote reali con sessioni separate: normale uscita del leader, cancellazione, errore callback e timeout; raccolta completa e CPU effettiva.
- Vero SIGKILL del supervisore, processo indipendente superstite, ricevuta nel DB originale e claim/fence ancora aperti fino alla risoluzione esplicita.
- Vero server HTTP indipendente, token e richiesta originale, SIGKILL durante il lavoro, recupero tramite API amministrative, replay della stessa approvazione e rifiuto di rieseguire la richiesta originale, **sia in COMMERCIAL sia in NON_COMMERCIAL**.
- Drain reale durante SIGKILL: la ricevuta originale può essere registrata senza aprire una nuova ammissione; il debito e il claim ancora attivi continuano a impedire il cutover.
- Vero adapter DSP backing e FFmpeg attraverso il registro, accounting e ricevuta kernel prima del completamento.
- Figli brevi contabilizzati, campioni proc vuoti insufficienti, processo estraneo lasciato vivo, processo di controllo ucciso senza falsa CPU/prova, tentativi di falsificare la ricevuta e rifiuto della perdita ACE con sola prova locale.

I writer di inferenza del test HTTP sono dichiaratamente sintetici e vengono iniettati soltanto nel bootstrap del test; il kernel, il server, i router, SQLite, le API token/amministrative e il protocollo di recupero sono reali. Non è una nuova inferenza neurale, un collaudo di accuratezza musicale o una revisione indipendente dei checkpoint.

Ruff completo `app native scripts tests` e parsing dei nove moduli modificati/aggiunti passano. Checker, soglie, opt-in e soppressioni di sicurezza invariati: **307 sorgenti app / 168 finding Bandit (0 HIGH, 21 MEDIUM, 147 LOW)**; 5 nuovi LOW di import/Popen revisionati esplicitamente, 5 identità spostate. C2 **173 confini**, runtime **554 sorgenti / 780 punti**, HTTP **30 siti / 21 file**. Il numero inferiore di punti runtime deriva dall'instradamento di cinque chiamate dirette nel runner condiviso e dall'aggiunta di quattro confini censiti; nessun checker modificato. Il gate HTTP iniziale richiedeva l'hash completo aggiornato di `ai_pull_worker.py`; la sola prova interessata è stata rieseguita dopo la review, mantenendo tutti i call-shape HTTP originali.

La regressione comprende claim, cgroup, perdita operatore, richiesta/replay, trasporto HTTPS/pull, ricevute modello, proprietà differite, drain e ingressi server/native. Le prove di finanza non interessata, modelli reali e Apple restano storiche, riusate soltanto per le parti byte-identiche. Nessuna nuova full CI o accettazione Windows/macOS/GPU/dispositivo/cgroup delegato viene dichiarata.

## Ripresa autosufficiente

Cumulativo: `MTA-0.3.0-r210-pre-RC-independent-guardian-cumulative.zip`. Leggere questo handoff, il JSON degli esiti e `DEVELOPMENT_COMPONENTS_R210.json`. B2 è chiuso con il metodo alternativo reale Linux; non ripetere questo blocco per ottenere un altro conteggio di test. Conservare la disponibilità del metodo cgroup e i suoi vecchi esiti, senza trasformare gli skip storici in pass.

Restano **A4,A5,A6,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6**: 8 criteri con implementazione/review residua e 5 collaudi target. Priorità successive: completare F4 per interpreti/runtime/checkpoint configurabili e la finanza generale/legacy che blocca C3/C5/D6. Il filtro adapter del pacchetto precedente non prova da solo il modello realmente caricato. B6 richiede host separati e partizioni reali; F5/G5/G6 e F6 mantengono i loro requisiti originali.

Nessun commit/staging/push/tag/release, dispatch CI, server/provider reale o download modelli effettuato. Dopo il commit dell'utente verificare Quality/SAST standard; non ripetere iOS/full CI invariati per questo solo aggiornamento. Commit suggerito cumulativo dopo4014a1f:

`Enforce model rights and recover crashed workers with independent Linux guardians`

## English handoff

Original B2 is now verified: an independent exec-isolated Linux subreaper survives actual supervisor SIGKILL, adopts/kills/reaps setsid descendants with pidfds, and records immutable original-scope quiescence only after kernel ECHILD. Five production model/preparation/native/pull call paths use the shared guarded runner on Linux; explicitly configured cgroups retain their separate implementation. The web process never becomes a global subreaper. Normal CPU uses exact reaped child-tree accounting, not proc samples or host telemetry.

Physical cleanup never settles money. Actual HTTP-token -> worker -> supervisor SIGKILL -> original journal -> authenticated admin recovery passes in both regimes, including idempotent approval and no original-request reexecution. Unknown usage remains unknown under explicit operator-funded loss. Guardian loss/missing proof retains the original job; no expiry takeover or PID guess. Local ACE client death cannot clear an external ACE service: that economic loss path is explicitly refused without external quiescence evidence.

628 distinct latest passing cases,16 new,zero current failures/errors/skips in the selected tests. Kernel and HTTP tests are real; synthetic inference writers do not certify neural models or rights. Source-bound gates/Ruff pass with unchanged checkers, thresholds and suppressions. Bandit307/168(0HIGH/21MEDIUM/147LOW),C2173,runtime554/780,HTTP30/21.

Original criterion text/weights remain unchanged. Progress29/42,69.0%,E complete,RCfalse. B6 and the other12 original residuals remain open. Last user-confirmed commit4014a1f; all later rights/adapter/guardian changes remain uncommitted. Input adapter-identity cumulative SHA25665f119b2c4194ecd84b7e582bfa9a98bd856eb251077638e0402b8c47bd2bf9c with4939 paths/694 original logs is retained. Reuse source-identical historical evidence and continue F4/general financial work;do not repeat the completed B2 implementation or dispatch remote workflows automatically.
