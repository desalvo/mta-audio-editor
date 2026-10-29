# B5 — Proprietà e metering di tutti gli ingressi AI

28 ottobre 2026 · MTA 0.3.0-r210 PRE-RC · baseline committata `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`.

**B5 verificato: 26/42 criteri originali, 61,9%, rispetto a 25/42 (59,5%).** Nessuna macroarea intera è ancora conclusa: 0/7. RC falsa e transizione finanziaria globale non autorizzata. Il criterio conserva formulazione e peso originali: “Prove ownership/metering for every legacy/local/native executor entry”. Nessuna certificazione di modelli, diritti indipendenti o hardware deriva da questo lavoro.

L'inventario `security/AI_EXECUTION_REVIEW_R210.json` distingue esecuzione server registrata, workflow web, worker pull, remoto durevole, esecuzione locale nativa e remota nativa, adattatori figli, Core ML locale, diagnostica esplicita dell'operatore e operazioni senza inferenza. Ogni ingresso individuato ha una classificazione e prove identificabili; tutti i sorgenti runtime sono vincolati anche quando non corrispondono ai pattern del censimento. Il censimento aiuta la revisione manuale e non è un analizzatore universale di codice arbitrario.

## Correzioni funzionali

- Il runner registrato interno ora esige sempre il proprietario realmente attivo della coda; non basta passare un identificativo utente. Controlla anche account attivo e appartenenza/non revoca del token opzionale. L'attesa FIFO non estende le credenziali; lo stesso controllo è ripetuto durante l'esecuzione e prima della pubblicazione.
- Anche l'ingresso JSON applica la validazione ricorsiva già usata dal trasporto audio: path, comando, eseguibile, shell, directory di lavoro e sorgenti non possono essere nascosti in oggetti o liste annidati. La validazione precede la coda.
- I byte WAV sono verificati prima di creare ledger/claim. Un input invalido non lascia una finta lavorazione economica in corso.
- La cancellazione del processo conserva la misura `wait4` del figlio realmente raccolto: CPU effettiva registrata nel ledger, stato cancellato e nessun risultato pubblicato. Non si cambia una tariffa o si deduce CPU/GPU dalla durata della richiesta.
- Un errore del controllo periodico non lascia più un figlio zombie. Il supervisore distingue l'aver ricevuto uno stato da `wait4(..., WNOHANG)` dall'aver effettivamente raccolto il figlio. Il primo campionamento con PID zero non è una prova di terminazione.
- Albero dei processi non verificabile o misura persa conservano ledger, fence, claim e riserva originali. Non diventano completamento a costo zero, nuova esecuzione o rilascio implicito del dispositivo. Le API JSON/audio restituiscono `409`, `worker_evidence_pending`, identificativo del lavoro originale e `retry_execution:false`, con cache privata disabilitata. La lettura delle risorse indica `unverified`; gli stessi identificativi non eseguono di nuovo il worker.

Una perdita di misura dopo l'avvio è distinta da un rifiuto verificabile prima dell'avvio (`WorkerNotStarted`). Solo quest'ultimo può chiudere come mancato avvio senza attribuire risorse inventate. Il recupero di processi esterni e l'eventuale perdita finanziaria continuano a usare i workflow originali con prove/operatori; non viene introdotta pulizia automatica per PID, timeout o assenza di osservazioni.

## Perimetro completo degli ingressi

Il censimento vincola **539 sorgenti** in `app`, `native`, `mobile` e `scripts`, inclusi browser e sorgenti nativi. Rivede **779 punti**: 528 handler HTTP, 174 confini di processo, 72 chiamate di inferenza e 5 punti Core ML nativi. Molti handler riguardano amministrazione, dati o diagnostica: **779 non è il numero di motori AI**. Ci sono 18 tipi incorporati e un contratto unico per le estensioni dell'operatore.

| Famiglia | Proprietà e contabilizzazione |
| --- | --- |
| Token/API server e Studio | Identità autenticata originale, FIFO durevole, ledger, decisione di licenza, claim/fence; controllo attuale di account/token prima del dispatch e del risultato |
| Lyrics/chords/markers, stem, Arranger/Remix e Studio web | ACL del progetto e attore persistito; ogni inferenza server passa al runner registrato; gli ingressi sincroni server incompatibili restano rifiutati |
| Pull HTTPS | Autorità Linux fissata, ledger/attore originali, credenziale del nodo, nonce e input della task; stato privato del worker vieta la riesecuzione incerta |
| Remoto durevole | Associazione richiesta/worker/lavoro originale, misura CPU autenticata e outbox di pubblicazione/fatturazione; nessuna sostituzione locale o doppia contabilizzazione |
| Native locali desktop | Profilo single-user esplicito e policy prima del modello; attore locale zero senza ledger o addebito server, supervisione delimitata e cancellazione |
| Native remote | Token privato dell'utente e journal della richiesta originale; contatori dal server proprietario, nessuna fattura locale aggiuntiva |
| Adattatori e processi figli | Esecuzione nel confine del genitore registrato/nativo/diagnostico; non producono autonomamente un addebito utente; misura non provata resta incerta |
| Core ML iOS / Android WebView | Operazione locale iOS esplicitamente non fatturata, sorgente sotto accesso nativo e cartella temporanea privata; importazione server soggetta ad ACL. Android usa gli ingressi server autenticati e non ha un secondo sink neurale indipendente |
| Installazione/self-test/benchmark | Comandi espliciti dell'operatore OS o dell'amministratore autenticato, distinti dal lavoro AI dell'utente e mai usati come uso fatturabile dell'utente |
| Codec, export, PCM, VST e altri handler | Operazioni senza inferenza; conservano i propri confini di autenticazione e ammissione e non inventano contatori AI |

Il controllo `scripts/check_ai_execution_inventory.py` rifiuta sorgenti/handler nuovi o cambiati, ingressi omessi, classificazioni mancanti, prove assenti, checker modificato e contratti di famiglia incompleti. Risolve alias di importazione per ambito lessicale: un import locale in una funzione non riscrive il significato della chiamata in un'altra. Le prove negative includono alias di eseguibili/modelli, nuovi endpoint generici `api_route`, modifica di sorgente mobile e omissione della famiglia nativa.

Il confine considera eseguibili installati dall'operatore attendibile, non il confinamento di codice arbitrario ostile. Il metering `wait4` conserva i limiti osservazionali e di processo già documentati; un campionamento non è attestation kernel. Il workflow cgroup e la prova di quiescenza esterna rimangono B2. La revisione B5 non equivale a provare gli eseguibili opachi o i checkpoint caricati: F3/F4/F6 rimangono aperti.

## Prove, difetti trovati e riuso

**271 casi distinti passati nel perimetro interessato**, **59 nuovi** (unione degli esiti più recenti), zero fallimenti/errori/skip. Il nucleo finale è in `validation/r210/execution-entry-final.xml` (249 pass); la rifinitura delle risposte di cancellazione è in `execution-entry-cancel-response.xml` (28 pass, sei già presenti nel primo rapporto). Esiti dei singoli step del nucleo e provenienza dell’unione sono in `execution-entry-progress.jsonl` e `execution-entry-result.json`. Non vengono sommati i tentativi intermedi o le ripetizioni.

Le prove attraversano davvero token/API, SQLite, coda, creazione del processo, CPU `wait4`, claim/fence, snapshot licenza, risultato e rifiuto dell'altro proprietario. Tutti i **18 tipi incorporati** e un'**estensione configurata dall'operatore** attraversano lo stesso percorso; il worker di protocollo è una fixture eseguibile e non un modello ML. Misure, processi e API delle nuove prove positive non sono rimpiazzati da mock. Sono verificati anche revoca durante FIFO, revoca durante esecuzione reale, cancellazione con CPU positiva, mancata riesecuzione e rifiuti privati JSON/WAV quando l'evidenza è incerta. L'incertezza dell'albero o del sensore è iniettata esplicitamente, mantenendo processo e raccolta reali.

Tre difetti iniziali sono riprodotti anche sul sorgente esatto del cumulativo della baseline: ingresso interno senza coda attiva, token revocato ancora accettato al dispatch e misura persa su cancellazione (`execution-entry-repro.xml`: tre fallimenti attesi sulla versione precedente). La nuova prova di perdita del sensore ha poi scoperto il figlio non raccolto, corretto prima del verdetto finale. Un caso di test iniziale tentava di associare il token a un utente inesistente, incontrando correttamente il vincolo FK: la fixture ora crea l'altro utente reale. Due vecchi test interni ora usano una vera identità account/coda, conservando le asserzioni originali. Una prima invocazione cumulativa è stata interrotta dal limite locale di 80 s, senza verdetto positivo; la successiva completa termina con 249 pass in 81,17 s. Nessun timeout o tentativo incompleto conta come successo.

Le ultime quattro prove API JSON/WAV hanno riprodotto anche una risposta interna non gestita dopo la revoca durante il lavoro e un503 improprio sulla cancellazione precedente all’avvio. Entrambi ora producono409 privato, `worker_cancelled`, `retry_execution:false` e un tombstone durevole `cancelled` per la richiesta originale; nessun polling rimane falsamente in attesa di un risultato. La rifinitura è verificata con28 casi API/cancellazione remota,senza ripetere il nucleo invariato di249.

Ruff e compilazione dei file modificati passano. Bandit 1.9.4: **299 file, 164 finding revisionati, 0 HIGH / 21 MEDIUM / 143 LOW**, senza suppressioni o checker allentati. Due identità di finding del supervisore sono state rivedute esplicitamente dopo lo spostamento/aggiornamento del codice; conteggi invariati. Trasporto: **30 siti / 21 file**. Ammissione C2: **170 confini / 299 sorgenti**, con revisione aggiornata alle stesse modifiche. Il gate B5 verifica anche tutti i sorgenti runtime fuori da `app`.

Gitleaks 8.24.3 sul delta testuale completo introdotto rispetto al cumulativo della baseline: zero finding, configurazione/allowlist invariate. Il delta finale del package viene verificato anche dopo l’aggiornamento delle prove e del manifest.

La full CI verde `40584085026` su `4c3c73a` resta la prova della baseline e dei confini non modificati. Sono riutilizzate le prove precedenti di coda/deferred, pull HTTPS e controlli native/remote per il codice invariato. Non è stata rilanciata una full CI né ripetuta la UI Chromium invariata. Questo delta non è ancora confermato da una nuova CI GitHub. Nessuna dipendenza, workflow, soglia, ignore o allowlist cambia.

## Stato, consegna e ripresa

Restano **16 criteri originali**: 11 funzionali/diritti (A4,A5,B2,C3,C5,C6,D6,E4,F3,F4,F6) e 5 target/ambiente (A6,B6,F5,G5,G6). Le formulazioni originali sono conservate in `DEVELOPMENT_COMPONENTS_R210.json`. Build native positive non sono prove di uso installato, modelli, GPU, diritti NC o hardware; il target iOS rimane inoltre privo di IPA firmato, come documentato nel checkpoint full CI.

Prossima chiusura integrata: **C3+C5+D6+E4**, riutilizzando C2 ed E5. Non ricostruire B5 o ripetere i 271 casi senza una nuova modifica rilevante. Usare le capacità e le prove ora censite per il restante audit finanziario e il cutover, senza sostituire i gate globali attualmente falsi con il semplice verde del censimento.

Cumulativo completo: **MTA-0.3.0-r210-pre-RC-execution-ownership-cumulative.zip**. Conserva ogni file precedente, asset, licenza, manuale, i 614 log originari e i modi dei file. Il manifest completo è `validation/r210/work-source-manifest.json`. Per istanze con ammissione C2 già attivata, il cambio di build segue la procedura di drain/upgrade originale in `SERVICE_ADMISSION_DRAIN_R210.md`; non eliminare journal o lavoro incerto per sbloccare un aggiornamento.

Nessun commit, staging, push, tag, release, dispatch CI o modifica di GitHub/server/provider reali è stato effettuato. Il prossimo commit, gestito dall'utente, include soltanto questo delta successivo a `4c3c73a` e la documentazione cumulativa:

```text
Close AI execution entry coverage and preserve cancellation metering
```

## English handoff

Original B5 is accepted without changing its wording or weight: **26/42 (61.9%), zero of seven whole macroareas, PRE-RC**. Complete runtime review binds 539 source files and explicitly classifies 779 observed HTTP/process/inference/native points into ten ownership/metering families. Counts include non-inference routes and are not a model count. All 18 built-in worker kinds and one operator extension traverse real APIs, SQLite, child processes and CPU measurement with original owner, license snapshot, claim/fence and replay/foreign-owner checks.

Internal dispatch now always needs the active original scheduler/account/optional token. Revocation during queue wait/execution is enforced; nested JSON control fields and invalid WAV are rejected before work or ledger admission. Cancelled worker CPU is retained. Observer failures now reap the exact child rather than leaving a zombie. Running or prelaunch cancellation returns private409 and keeps the original durable cancellation tombstone;no stale admitted polling or internal server error. Unknown tree/measurement retains the original ledger/claim/reservation and returns private typed HTTP409 without publishing, inventing zero usage or replaying inference. Native-local work remains explicitly unbilled and remote-native work is billed only by its owning server.

Latest affected regression: 271 distinct passes, 59 new, no failures/errors/skips. Current Ruff, compilation, source-bound Bandit/transport/C2/B5 inventories pass; no scanner/checker relaxation. Prior unchanged full CI/browser/remote/deferred evidence is reused. Model workers in the new transport matrix are executable fixtures, not actual neural models. Kernel quiescence, physical multihost, loaded checkpoint/independent rights, installed-OS NC and hardware acceptance remain the original separate open criteria. Global financial readiness and RC flags stay false. No Git or remote mutation and no new full CI were performed. Continue C3/C5/D6/E4 and the remaining independent gaps; use the cumulative archive and exact result JSON to resume without redoing this closure.
