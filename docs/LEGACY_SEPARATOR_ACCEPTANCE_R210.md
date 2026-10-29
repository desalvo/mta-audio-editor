# Demucs e lead/backing — confini legacy completati

29 ottobre 2026 · MTA 0.3.0-r210 PRE-RC · baseline confermata `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`.

**28/42 criteri originali verificati,66,7%,E completa1/7;RC falsa. Nessun criterio promosso in questo blocco:l’aumento della percentuale richiesto non è ancora conseguito.** Le correzioni qui sotto completano questi percorsi funzionali,non l’intero F4. Formulazione,peso e stato dei42 criteri restano invariati.

Input ripristinato:MTA-0.3.0-r210-pre-RC-model-selectors-cumulative.zip,SHA256 `ba9dbc8cc52c03a7d4fbe025b887b1f9a00f58b959f4a70722308f424b0bc5c4`,98.702.553byte/4740file. Il workspace era fermo al vecchio admin-cutover:è stato conservato separatamente e ripristinato l’ultimo archivio con SHA/CRC/modi originali. Nessuna nuova analisi o suite completa della baseline è stata ripetuta.

## Comportamento corretto

`DemucsStemSplitter.split()` è un ingresso diretto usato anche dal desktop e dalle diagnostiche. Prima passava al runtime senza leggere la policy Demucs,nonostante il parent/API avesse già i propri controlli. La riproduzione sull’AST del metodo originale raggiunge la sonda runtime con Demucs disabilitato;il codice attuale rifiuta prima della sonda e dell’output. Non è una prova di caricamento di un checkpoint reale.

Ora la richiesta iniziale e il modello eventualmente scelto dalla cardinalità devono appartenere allo stesso registro Demucs dichiarato. Una richiesta estranea non viene mascherata dalla selezione automatica di2/6/8stem. La policy corrente viene controllata prima degli effetti,dopo i callback di avanzamento,prima della chiamata al backend e prima di restituire i risultati. La variante frozen conserva l’esecuzione in-process,le eccezioni e il ripristino di `sys.argv`;il processo esterno conserva interprete/dispositivo e argomenti separati. Una revoca durante la vera esecuzione del processo di fixture ne impedisce la consegna del risultato. Non si promette l’interruzione istantanea di un kernel nativo già avviato.

Il permesso generico Demucs non autorizza più `MTA_DEMUCS_LOCAL_REPO`,neanche nel percorso frozen che prima lo ignorava. I repository/checkpoint personalizzati richiedono un’integrazione con diritti e identità revisionati separatamente;non basta rinominare una voce di catalogo. Le normali varianti Demucs dichiarate restano supportate. I profili personalizzati possono ancora descrivere cardinalità ma non conferiscono il diritto di eseguire checkpoint estranei.

Il caricatore condiviso audio-separator accetta soltanto i nomi file dei tre checkpoint lead/backing dichiarati applicabili a quel runtime;Mega53 continua il proprio percorso separato. Path,nomi arbitrari e filename di altri motori sono rifiutati prima di `load_model`. La policy effettiva viene riletta prima/dopo il caricamento e prima/dopo `separate`;un tag privato lega l’istanza al selettore effettivamente caricato. Un caricamento fallito o revocato non lascia un’ammissione precedente utilizzabile tramite MTA. Ogni callback ROCm ricontrolla i diritti prima del chunk successivo. Entrambi i chiamanti desktop/server usano lo stesso punto di inferenza protetto.

`MTA_LEAD_BACKING_COMMAND` non è più un esecutore AI arbitrario. Non aveva un contratto di identità/checkpoint/diritti e poteva usare il permesso DSP o di un altro modello. Ora la sua presenza rifiuta l’ammissione prima di routing,processo e ledger,anche nelle API token JSON/WAV e nel worker diretto. Il vecchio branch eseguibile è rimosso. Non è introdotto un flag con cui dichiarare arbitrariamente il comando “locale” o “autorizzato”. Il runner di processo interno resta disponibile per gli adattatori fissi già supportati e per le diagnostiche esplicite dell’operatore.

Il worker unificato prima trattava `ffmpeg-center-side` come un modello da caricare con audio-separator. Ora usa la stessa funzione DSP esplicita del desktop. I due WAV stereo conservano `(L+R)/2` e `(L-R)/2` con lato destro inverso,senza importare un modello neurale. Il processo FFmpeg ha timeout,log delimitato e pulizia del figlio;resta nel gruppo originale del worker. In questa sola modalità il runner arresta/raccoglie il proprio figlio e non segnala il gruppo condiviso. Il comportamento predefinito degli altri adattatori mantiene la sessione separata.

Questo non trasforma wait4 in un sensore dell’intero albero. La vera prova del worker registrato con discendente FFmpeg conserva correttamente job e claim originali in sospeso quando manca metering cgroup valido. Nessun completamento a zero,charge inventato,nuovo tentativo o risultato pubblicato. L’esecuzione CLI diretta separata verifica realmente i due WAV e i campioni PCM;non viene presentata come fatturazione server riuscita. La DSP è una divisione centro/lati,non una separazione semantica neurale lead/backing.

## Migrazione operativa — IT / EN

Per configurazioni con `MTA_LEAD_BACKING_COMMAND`,rimuovere quell’impostazione e scegliere esplicitamente un modello supportato la cui policy sia ammessa,oppure `ffmpeg-center-side` se serve la sola divisione DSP. Un comando personalizzato richiede una distinta integrazione revisionata;non ripristinare il branch arbitrario per aggirare il rifiuto. Rimuovere `MTA_DEMUCS_LOCAL_REPO` per usare i modelli Demucs dichiarati. I checkpoint personalizzati non sono autorizzati dal nome di un motore o da una build riuscita. Non è stata modificata alcuna configurazione su server reali.

EN:Direct desktop Demucs now validates both the requested and cardinality-selected checkpoint and rechecks current permission before dispatch/result delivery. Unreviewed repository overrides and opaque lead/backing commands are refused before effects. Remove the legacy command/repository settings and select an admitted supported model,or explicitly choose center/side DSP. Arbitrary custom integration needs its own reviewed checkpoint/rights contract;there is no automatic permission migration. Loaded backing models and ROCm chunks cannot retain revoked permission. Server usage without complete descendant evidence stays held under the original claim.

## Prove e riuso

**286 casi interessati distinti passati,47 nuovi;zero fallimenti/errori/skip correnti.** L’unione usa l’esito più recente per ciascuna identità negli XML elencati in `validation/r210/legacy-separator-result.json`;non sommare tentativi o i precedenti274/507casi. Le nuove prove comprendono API token reali JSON/WAV,SQLite/FIFO/ledger,worker CLI con vero FFmpeg e confronto PCM,processo esterno Demucs di fixture,percorso frozen di fixture,revoca post-load/inferenza/chunk e arresto/raccolta del solo figlio. Nessun nuovo checkpoint neurale è scaricato o eseguito.

Gli XML iniziali conservano le fixture obsolete e la prima aspettativa impropria di fatturazione del discendente. Il test è stato corretto per richiedere la conservazione dell’incertezza,senza indebolire il supervisore. I vecchi test di argomenti SAM e filename sintetici ora usano i selettori dichiarati;asserzioni su escape degli output,assenza di shell,mapping e fallback restano. La precedente prova del runner verboso è stata spostata sul primitivo interno realmente ancora supportato;il workflow applicativo ora verifica il rifiuto del comando opaco.

Ruff completo e compilazione app/scripts passano. Bandit304sorgenti/165finding revisionati,0HIGH/21MEDIUM/144LOW:nessun finding nuovo,uno LOW rimosso con il vecchio subprocess DSP duplicato. Quattro contesti cambiati sono revisionati esplicitamente e le altre identità di riga riallocate. C2:170confini;HTTP:30siti/21file;runtime:548sorgenti/781punti. Due inferenze duplicate confluiscono nel punto condiviso;un subprocess duplicato è rimosso. Le diminuzioni del censimento non sono criteri di accettazione. Checker,soglie,ignore e suppressioni restano invariati. Gitleaks8.24.3 sul delta finale completo:zero finding.

I tre loader F3 `ai_studio_adapter.py`,`ai_model_bytes.py`,`ai_model_attestation.py` sono byte-identici all’ingresso. La decisione BasicPitch è confrontata con le funzioni originali:uguale. Si riusano le7 prove ONNX/HTTPS precedenti esclusivamente per quel confine invariato;nessuna nuova inferenza o certificazione del runtime locale. I7 vecchi skip opzionali restano aperti. Finanza,UI/Chromium e fullCI40584085026 sulla baseline4c3 non sono rilanciate e non vengono attribuite al nuovo delta come una CI appena eseguita.

## Residui e ripresa

F4 resta aperto per l’accettazione completa di tutti gli esecutori legacy/nativi/opachi e dei runtime dinamici. Il percorso Core ML iOS non ha ancora un contratto completo di ammissione corrente/offline dei diritti:è lavoro di codice,non solo un collaudo OS mancante. Le librerie/binari esterni richiedono un’accettazione completa dei propri confini;la revisione dei callsite Python non prova il confinamento di codice ostile. F5 resta l’esecuzione sui target OS e F6 la revisione indipendente di ogni checkpoint opzionale effettivo. Nessuno di questi è promosso dalle fixture generate.

Restano14 criteri:A4,A5,B2,C3,C5,C6,D6,F4,F6 di implementazione/diritti e A6,B6,F5,G5,G6 sul target. Le basi economiche originali legacy e lo storico/provider generale non sono risolti. C3/C5/D6 restano bloccati;RC falsa. Il kernel cgroup delegato,host indipendenti,provider sandbox e target native/hardware mancanti rimangono espliciti. Non classificare tutti i residui come soli blocchi esterni e non ripetere il sottoblocco Demucs/backing di questo documento.

Consegna unica:**MTA-0.3.0-r210-pre-RC-legacy-separators-cumulative.zip**,SHA256 adiacente. Include tutto l’ingresso4740file e tutti i618log originali byte per byte,asset/manuali/licenze e metadata/modi ZIP;manifest completo aggiornato. Nessun DB runtime,cache,modello o credenziale aggiunto. Nessun commit/staging/push/tag/release,dispatchCI o modifica GitHub/server/provider. Il commit rimane all’utente.

Suggerimento inglese cumulativo dalla baseline4c3,non eseguito:

`Complete execution safeguards, settlement recovery and legacy separator rights`
