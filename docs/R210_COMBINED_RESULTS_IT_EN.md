# r210 — correttezza dei risultati combinati / Combined-result correctness

21 ottobre 2026. Versione **0.3.0-r210**, invariata. Cumulativo di partenza: `MTA-0.3.0-r210-diffsinger-deep-cumulative.zip`, SHA-256 `413ac707cca6b91bafa4706a2a7fc675515915ad398b0924b73c46167dcdb33a`, verificato insieme al CRC di tutti i membri prima dell'estrazione. Nessun commit, push, tag, release o intervento su server reali.

## Italiano

### Correzioni effettive

1. **Riconciliazione di risultati vuoti.** Il protocollo esplicito `empty_reason=no-notes` è accettato anche in forma JSON/dizionario; il generico `parts=[]` resta invalido. Se tutti i modelli sono vuoti, il risultato conserva l'offset della regione e gli avvisi di tutti i modelli. Con tre modelli, se il preferito non trova note, il primo risultato effettivamente non vuoto diventa riferimento per confrontare gli altri; il report dichiara `primary_model` e `empty_models`. Le ipotesi originali rimangono alternative, non vengono inventate note o probabilità.
2. **Canali MIDI dopo Deep.** I processi dei singoli stem potevano riutilizzare il canale 1 per strumenti diversi. Il risultato combinato assegna ora indirizzi melodici distinti, escludendo il canale 10 e rimappando coerentemente note e controller, senza modificare pitch, tempi, velocity o programmi. Più stream nello stesso risultato rimangono distinti. La capacità MIDI 1.0 è di 15 canali melodici: oltre questa soglia le parti si conservano e viene dichiarato il riuso, con indicazione di usare strumenti per traccia o porte separate. Non si promettono 16 canali melodici indipendenti su una sola porta MIDI 1.0. Le alternative originali non sono rimappate.
3. **Fine dell'audio e padding.** Basic Pitch e YourMT3 limitano le note all'audio effettivo: intervalli interamente nel padding vengono esclusi, quelli che attraversano il confine vengono accorciati e i contatori compaiono negli avvisi. I valori temporali non finiti falliscono esplicitamente. Non viene applicata quantizzazione né aggiunta musicale. La dipendenza dal nuovo helper entra nell'impronta dei checkpoint, così un risultato precedente non viene recuperato come se fosse già corretto.
4. **Annullamento finale.** Deep scarta il risultato se l'utente annulla o il budget scade durante l'ultimo worker, oltre ai controlli tra gli stadi già presenti. La contabilizzazione lato server resta nel ledger esistente.
5. **Benchmark.** I risultati validi senza note sono valutabili con zero true positive e tutte le note di riferimento come false negative. Le classi esplicite voce/coro sono distinte dai programmi GM generati per riprodurle: un synth GM 53 non dimostra una voce riconosciuta. Restano il confronto esatto e il requisito di strumenti realmente abbinati; nessuna soglia è abbassata.

### Prove e loro significato

- Test mirati iniziali: **53 pass**, nessun fallimento, un avviso Starlette. Comprendono casi sintetici di protocollo, padding, controller, capacità canali, annullamento e compatibilità preesistente. Non sono inferenze neurali.
- Suite r210: **1.369 pass, 138 skip, nessun fallimento**, un avviso, 129,49 s. Le esclusioni riflettono i prerequisiti del nuovo ambiente; non equivalgono ai precedenti collaudi reali e non sono pass. La regressione generale finale viene riassunta nel JSON e nell'addendum in fondo.
- Core audio C++ compilato da sorgente con CMake e GCC. Log incluso; questa compilazione non attesta dispositivi fisici o plugin esterni.
- Il risultato Deep PS reale registrato nel ciclo precedente è stato rielaborato con il nuovo instradamento: **10 parti, 55 note, 8 alternative**, contenuto musicale delle note invariato salvo canali, alternative identiche. Sono stati esportati e riletti SMF 0 e 1: tutte le 55 note conservate, canali/pitch corretti e tolleranza temporale di 1 ms dovuta ai tick. File e audit inclusi.
- Il mix originale dura 3,5 s; tutte quelle 55 note erano già dentro i suoi confini. La correzione del padding **non risolve** il benchmark precedente. Anche la rimappatura dei canali lascia le metriche identiche.
- Non è stata eseguita una nuova inferenza neurale in questo ciclo: il precedente ambiente temporaneo con venv e pesi installati era stato azzerato. I resoconti, WAV e risultati delle inferenze precedenti sono conservati e riconosciuti come evidenza storica, non riclassificati come nuove esecuzioni.
- Il primo tentativo della suite r210 ha rilevato due asserzioni troppo restrittive nei nuovi test (non tenevano conto delle parti con soli controller, correttamente conservate) e i permessi eseguibili non ancora ripristinati nell'estrazione locale. I test sono stati corretti per verificare le parti con note senza eliminare i controller; i permessi sono stati ripristinati dai metadati originali ZIP. Log iniziale mantenuto; la ripetizione r210 è passata. Nessun controllo di produzione indebolito.

### Stato reale delle tre macroaree

| Macroarea | Sviluppo ed evidenza | Verifiche ancora aperte |
|---|---|---|
| AI Vocal Studio | Bridge DiffSinger ONNX, RVC/Seed-VC, testi/melismi e trasporti già implementati; prove CPU reali precedenti conservate | Pronuncia/naturalezza, profili Qixuan IT/FR e altre banche compatibili; target e licenze del concreto impiego |
| AI Multi-Track Audio-to-MIDI | YourMT3 noPS/PS, Basic Pitch, Transkun e Deep con ripresa; correttezza dei risultati combinati migliorata | **Accuratezza 10–16 strumenti non raggiunta**, valutazione di modelli/strategia su registrazioni autorizzate con riferimenti indipendenti |
| General MIDI | Sintesi/riproduzione/export implementati; precedenti prove reali su 128 programmi e 47 drum conservate; nuovi round trip SMF | Dispositivi MIDI/audio, OS, plugin e ascolto sul target |

Non è quindi corretto dichiarare che restino esclusivamente collaudi hardware. La bassa accuratezza del mix denso non è risolta da una suite verde, da una diversa assegnazione di canali o da un cambio GPU. Servono risultati musicali indipendenti che raggiungano il requisito; questo pacchetto non li inventa.

### Collaudi consigliati sul target

1. Seguire `R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md` per i runtime e le verifiche dei singoli asset, mantenendo le policy e le revisioni fissate. La banca Qixuan completa è invariata e rimane separata dal sorgente.
2. In Deep controllare importazione delle parti, programmi e canali in riproduzione/SMF; con più di 15 stream melodici usare strumenti per traccia o porte separate. Controllare che annullare nell'ultimo stadio non pubblichi un risultato.
3. Provare regioni non allineate alla finestra del modello: nessuna nota deve proseguire nel padding oltre la fine dell'audio. Rivedere gli avvisi di taglio e tutte le note.
4. Provare una regione silenziosa e la ripresa del job: deve risultare esplicitamente nessuna nota, senza tracce fittizie e senza perdere l'offset.
5. Valutare la qualità su materiale autorizzato con ground truth indipendente, mantenendo separati note/timing, identità strumentali, pronuncia e ascolto. Non conteggiare un numero di parti come accuratezza.

## English

This cycle fixes empty-score region preservation and three-model primary fallback; routes combined Deep parts onto distinct available MIDI channels, including their controllers; bounds Basic Pitch/YourMT3 note intervals to actual source duration; invalidates old stage results when the timing helper changes; and rejects final Deep publication after cancellation/timeout. Valid no-notes benchmark inputs now produce honest zero-recall metrics. Explicit singing classes cannot match generated GM playback proxies accidentally.

The existing actual Deep PS output was reprocessed and exported/read as SMF types 0 and 1: 55 notes, channels/pitches preserved and timing within 1 ms. Original alternatives are untouched. This is **stored-output reprocessing, not new neural inference**. The old temporary neural environments were reset. Earlier real-inference evidence is retained as historical evidence. Routing and padding fixes do not turn the failed dense ten-instrument benchmark into a pass; its existing notes already fit inside the source audio.

MIDI 1.0 offers 15 melodic channel addresses on one port. More parts are preserved with an explicit reuse warning; independent playback then needs per-track instruments or multiple ports. No original hypotheses are discarded to improve accuracy figures. Version, legacy AI, VST SDK, licensing and billing policy remain intact. Full three-area completion is **not certified**: multi-instrument accuracy, Qixuan IT/FR language review and actual target acceptance remain distinct open gates.


## Modelli alternativi: verifica di fattibilità / Alternative-model review

Fonti primarie consultate il 21 ottobre 2026: [MR-MT3 autore](https://github.com/gudgud96/MR-MT3), [card dei pesi](https://huggingface.co/gudgud1014/MR-MT3/blob/main/README.md), [MT3-Infer](https://github.com/openmirlab/mt3-infer), [Magenta MT3](https://github.com/magenta/mt3).

MR-MT3 pubblica codice e checkpoint e dichiara MIT; la ricetta originale usa Python 3.10 con TensorFlow 2.11, Transformers 4.18 e altre dipendenze datate. MT3-Infer propone discendenti PyTorch, esclude il Magenta JAX originale e dichiara che il codice MT3-PyTorch vendorizzato non ha una licenza upstream dichiarata. Il progetto dichiara inoltre verifiche hash di download non uniformi fra backend. Sono elementi per una revisione separata di sorgenti, pesi e dipendenze, non un'autorizzazione ad attivare tutte le componenti. Nessun modello di queste famiglie è stato scaricato, abilitato o dichiarato verificato in questo ciclo. Non è dimostrato che uno di essi superi il mix MTA corrente.

The original MR-MT3 recipe and the newer wrapper have different runtime requirements and component boundaries. Published checkpoints or wrapper speed claims do not establish MTA accuracy. Safe pinning, individual component review, actual integration and inference remain necessary before activation; no model-download or license check was bypassed.

## Regressione generale finale / Final general regression

**4598 passed, 98 skipped, 6 warnings in 546.69s (0:09:06)**. Zero failures/errors. Esclusioni raggruppate con le motivazioni esatte in `validation/r210-combined-summary.json`; dettagli per caso nell'XML. I prerequisiti assenti dopo il reset includono runtime/asset neurali e strumenti di collaudo facoltativi; non sono dichiarati passati sulla base delle prove precedenti. Il core C++ è stato compilato prima dei test che lo richiedono. Gli ambienti di dipendenze, cache e modelli non vengono incorporati nel sorgente.

All new functional source changes were in place before final general collection. Area and focused counts overlap this run. Ruff passed. Original legacy/SDK members and executable ZIP metadata are verified separately in the package audit. The compact suggested commit is one line and cumulative in scope; the precise last Git commit cannot be established from a source-only archive.
