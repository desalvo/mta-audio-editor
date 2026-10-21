# Workflow Studio e controller MIDI — 0.3.0-r210

## Stato effettivo

Questa integrazione collega elaborazioni reali al progetto MTA e alla coda globale. Non completa ancora le specifiche integrali di AI Vocal Studio e AI Multi-Track Audio-to-MIDI. Non contiene un cantante sintetico, un classificatore multistrumento o compatibilità GPU dichiarata senza test.

| Operazione | Stato | Limite verificabile |
|---|---|---|
| Sorgenti audio indipendenti → MIDI | Implementata, verificata CPU | Basic Pitch ONNX, fino a 32 sorgenti; regione massima 10 minuti per job. Non riconosce gli strumenti dal mix né la batteria. |
| Melodia MIDI → armonie MIDI | Implementata, verificata localmente | 2–8 parti, intervalli vocali configurabili via API, priorità accordi confermati, voce superiore conservabile. Stile SATB; nessun canto audio. |
| Audio → MIDI → armonie → salvataggio | Verificata localmente | Due sorgenti sintetiche reali, inferenza ONNX e worker di armonizzazione; riapertura del progetto e ledger CPU. Non è una prova qualitativa su brani reali. |
| Corsie MIDI | Implementate, verificate Chromium | CC, pitch bend 14 bit, pressione canale/polifonica, programmi, selezione multipla, snap, frecce e undo/redo. |
| Sintesi/conversione vocale | Non implementata / diritti da verificare | Nessun modello/voicebank autorizzato IT/EN/FR integrato. Schede Cantanti/Espressione espongono il limite senza simulare risultati. |
| Mix completo → parti strumentali classificate | Non implementata | Capacità di import/editor di almeno 16 parti già verificata; non equivale alla capacità di trascrizione del modello attuale. |
| ASIO e matrice I/O hardware completa | In sviluppo, non completata | Restano prove e implementazione del backend dedicato; non vengono sostituite da selettori dimostrativi. |

## Installazione del modello

Aprire un progetto, sidebar **MIDI**, **AI Multi-Track Audio-to-MIDI**, scheda **Esecuzione**, **Modelli Studio e impostazioni** (admin). Verificare le licenze collegate, selezionare l'accettazione e premere **Installa e verifica**. Non parte alcun download implicito all'apertura della finestra.

L'installazione usa Python 3.11/3.12 separato in `.studio-models/basic-pitch-0.4.0-onnx-v1` sotto la directory dati dell'app. Non sostituisce PyTorch, NumPy o il runtime ROCm dell'installazione esistente. Sono necessari accesso agli indici Python, spazio sufficiente e un interprete compatibile; nelle native con Python più recente occorre rendere disponibile Python 3.11/3.12. L'installazione automatica di tale interprete non è implementata.

Il modello viene attivato solo dopo checksum e inferenza reale su un tono di riferimento. Sono visibili fase e stato del job; non viene inventata una percentuale per pip/inferenza. L'admin può ripetere un test reale, abilitare/disabilitare o disinstallare; la presenza di job Studio attivi o in coda impedisce la disinstallazione. Il blocco del runtime protegge anche le inferenze remote che usano lo stesso backend.

Il controllo rapido verifica il rilevamento del tono, non accuratezza generale o compatibilità ROCm/CUDA. ONNX è forzato su CPU; `ORT_DISABLE_TELEMETRY=1` precede l'import di ONNX Runtime e viene inoltre invocata la disattivazione API. I thread ONNX sono limitati per evitare sovrallocazioni su host grandi.

## Uso e risultati

1. Selezionare sorgenti del tipo richiesto e regione (inizio/fine in ms). L'audio preparato rispetta tagli, posizioni delle clip, delay e gain; non applica gli insert FX o trasposizioni/stretch del mix. Il MIDI conserva l'offset della regione nel progetto.
2. Regolare le soglie della trascrizione oppure numero voci e tonalità dell'armonia. I programmi strumento possono essere assegnati nell'editor MIDI, senza inventare classificazioni automatiche.
3. Avviare. Valgono autenticazione, permessi, coda globale, quote/crediti e accounting del server. I crediti esauriti causano rifiuto prima del worker, con indicazione di controllare il profilo o contattare l'amministratore.
4. La finestra può essere chiusa: il job continua ed è consultabile nella lista globale. Il pulsante Annulla interrompe il worker; la pubblicazione atomica, una volta iniziata, termina prima di ulteriori azioni.
5. Se il progetto è rimasto invariato, l'import automatico salva le tracce prima dell'esito finale. Se viene modificato, il risultato viene conservato per **Rivedi e importa**, con revisione corrente esplicitamente confermata. Ripetere la stessa importazione non duplica tracce.
6. Risultati disponibili in JSON musicale comune e ZIP diagnostico autorizzato (stato, risorse, ricevuta di pubblicazione; nessun audio sorgente o credenziale). Gli stderr completi dei worker server restano nel journal diagnostico esistente.

Retry riutilizza solo sorgenti completate di un job dello stesso utente/progetto, con richiesta e revisione identiche. Un progetto cambiato richiede una nuova elaborazione; non vengono riusati risultati obsoleti. Le fasi non terminate vengono rieseguite. I checkpoint intermedi non sono una ripresa interna della rete neurale.

Timeout globale di default: 3.600 s, configurabile 60–14.400 s. Conservazione risultati/cache: sette giorni, configurabile 1–365; pulizia all'avvio e ogni ora per job terminali o cartelle orfane scadute. Le tracce già salvate nei progetti rimangono. Le cache Studio vengono eliminate anche dalla cancellazione completa dei dati utente. L'ultimo job viene ricordato separatamente per progetto e tipo di Studio nelle preferenze lazy.

## Corsie controller

Nell'editor MIDI aprire **Corsie controller**. Scegliere tipo, canale e numero CC/nota, aggiungere punti con doppio clic o campi numerici. Maiusc-clic aggiunge alla selezione; trascinamento e frecce spostano il gruppo, Alt ignora snap. Canc elimina, Ctrl/Cmd-Z annulla. Pitch bend usa valori grezzi 0–16383 (centro 8192), con scala grafica firmata. Le curve sono a gradini, come gli eventi MIDI effettivi: non introducono un'interpolazione nascosta. Zoom/scroll seguono il piano roll; gli eventi sono quelli della lista eventi e del salvataggio/esportazione MIDI.

## API e isolamento

- `GET /api/ai/studio/capabilities`: capacità effettive e candidati non abilitati.
- `POST /api/projects/{pid}/ai-studio/jobs`: operazione, track_ids, regione, settings, auto_import, retry_of opzionale. Nessun percorso o eseguibile scelto dal chiamante.
- `GET .../jobs/{job_id}`, `POST .../cancel`, `GET .../result`, `POST .../import`, `GET .../diagnostics.zip`.
- Admin: `/api/admin/ai/studio/models`, `/policy`, `/models/basic-pitch/install`, `/test`, PUT abilitazione e DELETE disinstallazione.

Il backend usa il protocollo worker preesistente. Partiture strutturate passano tramite un file privato validato (massimo 8 MiB), non un percorso fornito dal client. Output musicale massimo 16 MiB, budget eventi e 24 ore verificati dal formato comune. I job server con identità reale producono ledger CPU; native single-user non producono fatture. CPU/GPU non misurate non vengono inventate. Il client nativo remoto può usare l'endpoint token worker esistente; il collegamento completo dei nuovi workflow di progetto a un progetto locale tramite server remoto resta aperto.

## Licenze e blocchi

Ricerca primaria verificata il 20 ottobre 2026; mantenere separati codice, pesi, voicebank e dipendenze. Lo ZIP non redistribuisce modelli né ambienti Python installati.

| Componente | Evidenza / decisione |
|---|---|
| Basic Pitch | Codice e modello ONNX incluso upstream Apache-2.0; checksum `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`. Dipendenze transitive e distribuzioni binarie vanno riesaminate al packaging. |
| YourMT3 | Repository originale GPL-3.0; diritti dei checkpoint esterni e pipeline dipendenze non risolti in questo ciclo. Non abilitato. |
| MT3-Infer | Wrapper MIT, ma codice MT3-PyTorch vendorizzato dichiarato upstream senza licenza; non basta la licenza del wrapper. Non installato. |
| OpenVPI vocoders | Alcuni pesi esplicitamente CC BY-NC-SA-4.0: non attivati in un server con billing. Licenza vocoder e autorizzazione del cantante sono questioni separate. |
| Altri candidati vocali/trascrizione | Non abilitati senza versione, pesi/voicebank autorizzati, ricetta verificabile e inferenza reale. Nessuna compatibilità GPU presunta. |

Fonti: https://github.com/spotify/basic-pitch/blob/main/LICENSE ; https://github.com/mimbres/YourMT3 ; https://github.com/openmirlab/mt3-infer ; https://github.com/openvpi/vocoders/releases ; https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md .

Restano l'integrazione di sintesi/conversione e fonemizzazione/lyrics con voicebank autorizzati, trascrizione multimodello con riconciliazione e alternative, modelli/strumenti reali su dataset comparabili, GM installer multipiattaforma, ASIO/routing fisico completo e collaudo delle piattaforme native e ROCm di produzione. Nessuna certificazione server deriva dai soli test locali.
