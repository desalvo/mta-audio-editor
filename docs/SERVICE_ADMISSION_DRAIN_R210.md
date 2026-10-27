# C2: barriera di ammissione e drain dell'intero servizio

MTA Audio Editor 0.3.0-r210 · 27 ottobre 2026 · PRE-RC

## Criterio originale e risultato

Il criterio **C2 — Distributed admission barrier and service-wide drain** è implementato e verificato sul deployment supportato da B4: un'autorità Linux con storage locale persistente, più processi API/timer della stessa build e worker indipendenti collegati soltanto tramite HTTPS autenticato. Il suo testo e il peso restano invariati. L'accettazione riguarda il protocollo di ammissione e quiescenza del servizio; non certifica HA, filesystem di rete o una nuova topologia a più autorità.

C2 passa da implementation_pending a verified. Avanzamento originale: **25/42, 59,5%, 0/7 macroaree**, contro24/42,57,1%. Nessun'altra promozione. C3,C5,C6,D6,E4,le verifiche finanziarie/diritti/kernel/target residue restano aperte. La RC non è raggiunta. I controlli globali di autorizzazione del cutover rimangono falsi: il nuovo protocollo non risolve obbligazioni finanziarie né autorizza un cambio di regime.

L'evidenza corrente,con identità dei casi,rapporti e hash,è `validation/r210/service-admission-result.json`. La revisione completa dei punti di ingresso è `security/SERVICE_ADMISSION_REVIEW_R210.json`,verificata da `scripts/check_service_admission_inventory.py`. Tutti i299 sorgenti Python dell'applicazione sono associati alla revisione;il censimento esamina170 confini espliciti di processo/thread/database/servizio/CLI. Modifiche ai sorgenti o nuovi confini rendono il gate obsoleto;non vengono accettati automaticamente.

## Comportamento verificato

La modalità `MTA_SERVICE_ADMISSION=authority-v1`,disattivata per default,conserva due file privati nella data root originale: `service-admission.sqlite3` e `service-admission.instance`. La generazione e la fase open/draining vengono serializzate con le ammissioni originali. Ogni nuova richiesta HTTP/WebSocket entra prima dell'autenticazione e resta contata fino alla fine di streaming e attività di risposta. Thread finiti,heartbeat,cancellazione remota e lettori di output hanno ticket figli indipendenti prenotati prima dell'avvio. Le sessioni di registrazione/VST3 mantengono ticket per tutta la loro durata;la chiusura lo rilascia soltanto dopo la pulizia effettiva.

Una barriera chiusa rifiuta nuovo lavoro. Il lavoro già ammesso conserva il contesto originale e può completare figli/pubblicazione/accounting. I worker HTTPS possono reclamare/completare soltanto assegnazioni originali già presenti,con le verifiche di nodo,nonce e proprietario esistenti. Login,letture amministrative e completamenti/cancellazioni originali selezionati restano disponibili;non possono creare un nuovo thread di lavoro. Gli endpoint di controllo delle sessioni mantengono le ACL originarie.

Gli scheduler dormienti non impediscono il drain;ogni ciclo effettivo necessita di ammissione. Questo vale anche per billing/storage sampling/installazioni/diagnostica invocati da CLI. Un riavvio durante il drain espone i controlli amministrativi e attende la ripresa esplicita prima di avviare recuperi e servizi periodici.

La lettura di stato tiene insieme fase,conteggio e audit. Non basta osservare zero thread: vengono controllati journal della coda,ricevute terminali,claim/fence originali,task pull,lease GPU,outbox di billing/pubblicazione,transazioni file,cancellazioni account e invii mail già spediti al trasporto. Evidenza mancante/corrotta o attività concorrente non vengono tradotte in zero. Le passività finanziarie complete restano un controllo separato C3.

Un processo perso,un'eccezione non verificata o una chiusura fallita lascia un'ammissione incerta. Non esiste una scadenza che la renda conclusa: PID,orologio o idle timeout non provano quiescenza. I reaper possono avviare la chiusura reale di una sessione inattiva;solo una chiusura riuscita rilascia il ticket. Il recupero generale delle incertezze con prove esterne resta nel lavoro B2/C6;non cancellare record o file per ottenere `drained:true`.

## Condizioni di deployment

- Tutti i processi API e i timer dell'autorità devono usare questa build e la stessa data root locale sul medesimo host Linux. I worker HTTPS hanno una root privata e non montano SQLite dell'autorità.
- Prima della prima attivazione,arrestare con la normale manutenzione i processi delle build precedenti e verificare il lavoro originale pendente. Avviare tutti i processi partecipanti con il flag già configurato. L'attivazione a caldo con repliche vecchie/non partecipanti non è supportata.
- Non distribuire codice modificando i file Python di una build già in esecuzione. Ogni build viene associata ai byte effettivi di tutti i sorgenti Python;le repliche differenti non possono ammettere nuovo lavoro contro una build fissata diversa.
- Non usare NFS,SQLite condiviso con i worker,autorità concorrenti o una presunta lease HA. Le prove di perdita/partizione su host fisicamente distinti restano B6/C6.

Nessuno di questi passaggi è stato eseguito sul server dell'utente. Il protocollo resta opt-in e il cambio generale di regime resta disabilitato.

## Procedura amministrativa

Gli endpoint richiedono una sessione reale di amministratore attivo. Le scritture richiedono anche `X-MTA-Request: 1`;booleani,generazione e identificativi devono essere esatti. Le risposte sono private e no-store.

1. Leggere `GET /api/admin/service-admission`. Se enabled è false,il protocollo non è attivo. Se è attivo,conservare generation,phase,pinned_build e drain_id.
2. Per iniziare,usare `POST /api/admin/service-admission/change` con la generazione appena letta,`draining:true`,un nuovo identificativo stabile e `confirm:true`. Esempio di corpo,solo se la generazione letta è0:

```json
{"expected_generation":0,"draining":true,"identifier":"maintenance-20261027-001","confirm":true}
```

3. Rileggere lo stato. `drained:true` richiede fase draining,build coincidente,nessuna ammissione attiva e audit verificato senza lavoro pendente. Controllare active_by_source,pending.by_kind,pending.reasons e l'audit. È una fotografia coerente,non un'autorizzazione finanziaria. Una risposta indisponibile invalida il risultato precedente.
4. Per riaprire,usare lo stesso identificativo originale,la generazione corrente,`draining:false` e `confirm:true`. Le ammissioni incerte restano conservate anche dopo una riapertura;non vengono assolte o convertite in completamenti.
5. Dopo una risposta persa,ripetere soltanto la medesima operazione originale e rileggere la fase effettiva. Una generazione o identità diversa produce conflitto. Non inventare un nuovo ID per sostituire un drain già iniziato.

Nuovo lavoro HTTP rifiutato riceve503/no-store/Retry-After;un nuovo WebSocket riceve1013. I controlli di sessione/accounting vengono comunque verificati. La precedente correzione `database_busy` dell'export è conservata ed è verificata di nuovo dove cambia il confine di connessione.

## Aggiornamento della build fissata

Prima di sostituire una build attiva,chiudere l'ammissione e ottenere zero lavoro originale. Riavviare la nuova build mantenendo journal e instance. Il suo stato mostra build_matches:false e non dichiara il servizio drained. Solo un amministratore può chiamare `POST /api/admin/service-admission/upgrade` con `expected_generation`,il vecchio `expected_build` letto da pinned_build e `confirm:true`.

L'handoff richiede fase chiusa,zero ammissioni e audit originale verificato senza pendenti;registra un evento immutabile,incrementa la generazione e conserva tutti i record. La barriera resta chiusa. Riaprire esplicitamente con la nuova generazione e l'originale drain_id soltanto dopo il controllo. La vecchia replica non può più ammettere lavoro. Una build nuova non può assolvere lavoro incerto per rendere possibile l'aggiornamento.

## Backup e ripristino

Il backup amministrativo conserva ora lo snapshot SQLite coerente del journal,compreso il WAL tramite SQLite backup API,e la sua instance originale. Il ripristino offline su directory vuote convalida esattamente lo schema/trigger immutabili distribuiti:non accetta trigger o view aggiunti e non allenta il rifiuto di schemi eseguibili negli altri database.

Un backup può contenere richieste ancora aperte al momento della fotografia. Il loro stato incerto viene preservato dopo il ripristino:non si cancellano nonce,ticket o audit,non si deduce la fine dal vecchio PID e non si crea una barriera vuota per simulare un drain. Sorgente e clone non devono essere avviati come due autorità concorrenti. Il protocollo B4 conserva i propri vincoli di identità/worker;la quiescenza/recovery esterna non viene certificata da un backup.

## Accettazione e limiti

Le prove eseguono API/autenticazione/CSRF reali,più processi sul journal originale,un processo ucciso con SIGKILL,worker CLI HTTPS con risposte claim/completion perse,worker locale registrato con heartbeat e addebito unico,upload PCM reale con import/pubblicazione,backup/ripristino e un effettivo cambiamento dei sorgenti in una nuova build indipendente che impedisce l'ammissione della vecchia replica.

La durata della sessione VST3 viene verificata con un processo controllato reale al confine Session;questo non è una nuova prova di plugin,device o GPU. Le precedenti prove CI/native restano storiche e non vengono trasformate in nuova accettazione hardware. I casi C2 correnti non richiedono né contano skip di compiler/VST3 come successi. Nessun modello/provider reale o server esterno viene usato.

Il vecchio checkpoint `development-pending/C2_SERVICE_ADMISSION_WIP.patch` resta conservato come storia e non va riapplicato:il codice operativo corrente contiene l'implementazione completata e corretta. Non ripetere analisi/test già superati salvo modifiche al confine interessato. Il prossimo lavoro resta C3/C5/D6/E4 e le altre uscite originali;nessun denominatore è stato ristretto.

## English operator handoff

Original C2 is verified for the supported B4 deployment:one pinned local Linux authority with current-build API/timer replicas and independent authenticated HTTPS workers. Distributed admission and service-wide draining now cover full ASGI lifetimes,finite and helper threads,original capture/VST3 sessions,periodic cycles,one-shot billing/sampling/install/inference,original durable work and immutable instance/build/audit identity. Actual independent process/TLS response-loss/local worker/PCM publication/source-build handoff/backup tests pass. This does not authorize financial cutover,HA,NFS,external kernel quiescence,rights or hardware acceptance.

Default flag is off. Cold-start every participating authority process with `MTA_SERVICE_ADMISSION=authority-v1`,the same local persistent data root and current source build;do not activate alongside legacy/unaware replicas. Workers keep private state and never mount authority SQLite. Active administrator session plus CSRF marker and exact generation/ID/confirmation are required for begin/resume/upgrade APIs. Poll original state;unknown/lost work never expires. Resume keeps uncertain records. Upgrade requires an already held gate,zero original work and exact previous build,retains immutable history and keeps the gate closed. Old replicas then fail admission.

Backups retain the exact journal/instance pair and uncertain tickets;offline empty-root restore validates the bundled immutable schema. Never discard tickets,force-unlock SQLite or start source and restored clone as concurrent authorities. Persistent/lost external work requires the separate original recovery proof. RC remains blocked:25/42(59.5%),0/7macroareas. No commit,GitHub/provider/server mutation occurred.
