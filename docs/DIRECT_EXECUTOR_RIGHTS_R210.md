# MTA 0.3.0-r210 — Diritti sugli ingressi diretti e sui componenti offline

29 ottobre 2026, Europe/Rome. **PRE-RC:28/42 criteri originali(66,7%),E completa1/7. Nessun criterio promosso; l'aumento numerico richiesto non è raggiunto.** Completato il blocco funzionale degli adattatori diretti e wrapper di componente descritti qui. Non è tutta F4,non sostituisce F5/F6 e non autorizza la RC.

Baseline confermata:`4c3c73afe6d3829aad155c23f5f1bbb6d375433a`;commit differito all'utente. Questo cumulativo parte da `MTA-0.3.0-r210-pre-RC-partial-settlement-cumulative.zip`,SHA256 `e518810f084570f480181444fe284f6a0fb4a584ff018b337c4607b37dec2ab2`,4695 file. Mantiene tutti i delta precedenti di esecuzione,amministrazione,F3,merchant e settlement. La copia locale era già quella corrente: nessun ripristino vecchio o nuova analisi finanziaria. Nessun commit,staging,push,tag,release,dispatch CI o azione su GitHub/server/provider reali.

## Difetto e comportamento corrente

Il controllo del genitore non copriva ogni ingresso diretto. Un modello Whisper già caricato poteva ancora trascrivere dopo la disabilitazione della policy;un errore MPS poteva inoltre proseguire su CPU dopo la revoca. Il difetto è riprodotto sul corpo della funzione del sorgente originale:un modello sintetico viene chiamato una volta nonostante la policy disabilitata;il sorgente corretto lo rifiuta prima della chiamata. Prova:`validation/r210/direct-rights-baseline-repro.json`. Non è stata eseguita inferenza neurale in questa riproduzione.

Ora la policy locale corrente viene ricontrollata sugli ingressi diretti Whisper,inclusi modello caricato,estrazione progressiva e fallback MPS->CPU;Basic Pitch e dispatch Studio;YourMT3;MR-MT3 incluso il percorso di self-test;Transkun adattatore/CLI;DrumSep ONNX;SAM CLI;backend profilati Demucs/SAM;OddVoices;bridge,run e sessione ONNX DiffSinger. La matrice copre18 ingressi. Rifiuti precedono l'accesso ai sorgenti e i nuovi effetti output/cache/runtime. La disabilitazione commerciale generale e un'autorizzazione free-only in un regime commerciale vengono rispettate;una policy danneggiata non è un'approvazione. L'input malformato continua a usare le proprie convalide,senza creare lavoro.

Per il canto,il permesso dell'acoustic non vale per il vocoder:entrambi devono essere autorizzati. Il runtime ONNX ricontrolla anche tutti gli altri componenti dichiarati nell'inventario,per esempio un motore distinto,prima delle sessioni. I componenti non acquistano diritti dal semplice fatto di condividere un bundle o un modello già approvato. Le funzioni di sola diagnostica/inventario e i codec senza inferenza non vengono trasformati in lavori AI.

## Wrapper offline: contratto prima del codice esterno

`studio_offline_runner.py` non è più un pass-through per qualsiasi script. Prima dell'esecuzione richiede un ruolo MTA supportato;il ruolo seleziona le verifiche,non costituisce un permesso. Per RVC e Seed-VC ricontrolla manifest hash-verificato,abilitazione del bundle,tutti i permessi dei componenti,script esatto e directory runtime originale. Il wrapper Seed non può degradare al contratto RVC né viceversa. Per DiffSinger richiede i due permessi attuali e lo script fisso del formato selezionato:bridge ONNX MTA o `scripts/infer.py` del runtime configurato. Script estranei,modificati,componenti revocati o disabilitati e directory diversa vengono rifiutati prima di eseguire quel codice.

I produttori MTA propagano automaticamente `MTA_STUDIO_OFFLINE_KIND` e,per conversione,`MTA_STUDIO_CONVERSION_ASSET_ID`. Non sono campi dell'API utente. Non è possibile inventare un permesso passando questi nomi:il child rilegge il componente installato e la policy corrente. Restano attivi il divieto di auto-download Python,le verifiche dei checkpoint e l'importazione del namespace del runtime senza lo shadowing di `i18n` MTA. L'interprete e il codice installati dall'operatore restano nel confine di fiducia;non è un sandbox per un amministratore ostile o codice nativo arbitrario.

## Uso e migrazione — IT/EN

Gli ingressi server restano le API/job originali con proprietario,coda,claim,ledger e policy. Le app native continuano i propri workflow locali/remoti. Non esiste una nuova API,un grant automatico,una nuova dipendenza di produzione o una modifica della UI.

Le normali chiamate MTA impostano già il ruolo del wrapper. Chi lo invocava manualmente come generico esecutore deve usare il workflow del componente installato. Per una diagnostica isolata esplicita,RVC/Seed richiedono il ruolo corrispondente,l'ID esatto del bundle ammesso e la directory runtime del manifest;DiffSinger richiede il ruolo `diffsinger`,il runtime/formato configurato e i permessi distinti del cantante/vocoder. Un ruolo o un ID da soli non superano i controlli. Non ripristinare l'esecuzione arbitraria per aggirare un rifiuto. Il self-test MR-MT3 non ignora più una policy disabilitata.

EN:Normal MTA workflows set the component role automatically. Manual generic-script use is refused. Select the original installed component workflow,keep its current reviewed permissions and original runtime binding,and preserve separate singer/vocoder authorization. Role flags are selectors,not grants. A model already in memory,a profiling wrapper or a self-test does not bypass current policy. This change neither approves optional checkpoint rights nor certifies arbitrary operator binaries.

Il controllo si applica a nuove chiamate/inferenze. Non pretende di interrompere istantaneamente un kernel già in esecuzione o di confinare librerie native arbitrarie. Le prove e i workflow originali di cancellazione/quiescenza rimangono distinti.

## Verifica corrente e limiti

**507 casi distinti passati,99 nuovi;zero fallimenti/errori correnti e7 prerequisiti opzionali saltati.** Provenienza e unione per identità in `validation/r210/direct-rights-result.json`:non sommare tentativi o riesecuzioni. Le nuove prove usano la vera policy su file,un vero fence commerciale iniziale per i rifiuti di regime,quattro CLI indipendenti e un bundle RVC di soli byte propri installato/abilitato tramite il registro applicativo prima di eseguire il suo script come processo reale. Sono verificati revoca,fallback,rifiuto prima degli effetti,script/role/cwd errati,tampering e policy di un componente secondario. I checkpoint neurali delle fixture non sono modelli reali e i loro permessi di test non autorizzano quelli dell'utente.

**7 prove con Basic Pitch ONNX reale passano sul codice corrente.** Cinque verificano ricevuta diritti/caricamento/ledger e worker HTTPS indipendente,nei due regimi e con risposta persa/replay;due attraversano coda/CPU/artefatti e pipeline progetto effettive. L'adapter è cambiato,quindi la vecchia prova F3 non è stata dichiarata identica:i nuovi hash del caricatore entrano nel contratto verificato. Restano invariati il perimetro F3 `verified-pull-v1` e i rifiuti degli altri remoti. Non è accuratezza su brani reali né certificazione GPU/native/altri modelli.

Il runtime di test separato è dichiaratamente ONNX-only;versioni e self-test sono in `direct-rights-test-runtime.json`. La prima esecuzione dei cinque casi non disponeva di qrcode/FastAPI per gli import applicativi;aggiunti i prerequisiti locali,il self-test e tutti i cinque casi sono passati. I metadata upstream BasicPitch richiedono TensorFlow non installato in questo profilo:non si dichiara `pip check` pulito o packaging opzionale di produzione. Nessun runtime/modello incluso nell'archivio.

Corretto anche il trascinamento di FastAPI/qrcode nella sola lettura della policy da un interprete di modelli. Ora la risoluzione dei percorsi usa solo stdlib quando auth non è caricato;in un’applicazione già avviata conserva gli stessi percorsi auth iniettati. Rimangono identici i controlli su mirror,fence SQLite read-only,revisioni e transizione. Due processi reali Python -S,senza site-packages,verificano sia il rifiuto sia il passaggio autorizzato fino all’import del runtime opzionale,senza creare DB o output.20 casi core/epoch e7 prove ONNX sono rieseguiti dopo la modifica. I prerequisiti web installati nel primo tentativo di test non diventano quindi nuovi requisiti dei modelli o di produzione.

I7 skip riguardano voicebank CC0/core installato,YourMT3 reale,Torch per un test di metadata legacy,tre G2P eSpeak e un vecchio test di grafo ONNX sintetico in un altro interprete. Non sono successi e non chiudono criteri. I due vecchi skip BasicPitch sono invece sostituiti dalle due esecuzioni reali passate. Gli XML iniziali conservano anche le correzioni delle fixture:regime commerciale senza fence,permessi mancanti su soli byte generati e namespace incompleto nel double BasicPitch. Nessuna soppressione di errori del prodotto o policy globale permissiva nei test.

Ruff completo app/native/tests/scripts e compilazione passano. Bandit completo303 sorgenti/166 finding revisionati,0HIGH/21MEDIUM/145LOW,nessun nuovo finding. Quattro identità di riga riallocate e due launch DiffSinger con ambiente di ruolo esplicito sono riesaminate. Inventari correnti:171confiniC2,30sitiHTTP/21file,547sorgenti runtime/783punti. I quattro checker,soglie,soppressioni e ignore rimangono byte-identici all'ingresso. Gitleaks8.24.3 sul delta testuale finale completo:zero finding.

Si riusano le prove finanziarie/settlement e UI Chromium/axe invariate;nessuna nuova fullCI GitHub dichiarata. FullCI40584085026 resta riferita alla baseline4c3. Una CI futura sul commit cumulativo sarà una prova ulteriore,non è già stata eseguita.

## Stato originale e prossima uscita

Il blocco di ingressi diretti e wrapper di componente è completato. F4 resta aperto per l'accettazione completa di tutti gli esecutori legacy,nativi/opachi e dei runtime dinamici;un censimento e script propri non certificano ogni binario installato. F6 richiede la revisione indipendente dei checkpoint opzionali effettivi;F5 i target OS installati. Restano anche implementazione/review generali:non classificare tutto come assenza di ambiente. Non promuovere F4 da questa sola matrice o indebolire i suoi requisiti originali per muovere il punteggio.

Restano14 criteri: A4,A5,B2,C3,C5,C6,D6,F4,F6 di implementazione/diritti e A6,B6,F5,G5,G6 sul target. La finanza generale e le basi originali legacy non sono risolte da questo aggiornamento;C3/C5/D6 non si abilitano. Non ricominciare gli ingressi di questo documento,la riconciliazione parziale o il collector già completati. Continuare sugli esecutori/diritti non coperti o sugli obblighi finanziari originali con le prove necessarie;registrare i blocchi effettivi,senza inventare saldi o attestazioni.

## Consegna

MTA-0.3.0-r210-pre-RC-executor-rights-cumulative.zip preserva tutti i4695 file di ingresso,616 log originali byte per byte,asset,manuali,licenze,modi e attributi ZIP. I nuovi log descrivono soltanto fixture/prerequisiti locali. Manifest completo e preservazione inclusi. Nessun DB runtime,credenziale,cache o modello aggiunto. Non è una release.

Commit inglese cumulativo suggerito,non eseguito:

`Complete guarded execution, administration, settlement recovery and component rights enforcement`
