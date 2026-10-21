# MTA Audio Editor 0.3.0-r210 — Qixuan IT/FR, UI nativa e progetto musicale

21 ottobre 2026. Versione invariata; nessun commit, push, tag, release o intervento sui server reali.

## Italiano

Completato lo sviluppo software richiesto in questo ciclo per Qixuan IT/FR sulla banca esistente, zoom delle app native, tipi di progetto audio/MIDI, origine musicale e transport, quantizzazione e icone. I collaudi grafici e dei dispositivi reali restano distinti dalle prove qui eseguite. **Non viene dichiarato risolto il precedente obiettivo di accuratezza Audio-to-MIDI su 10–16 strumenti:** non è stato oggetto di nuove inferenze in questo ciclo e le precedenti prove negative sono conservate.

### Funzioni e correzioni

| Area | Comportamento consegnato |
|---|---|
| Qixuan IT/FR | Helper G2P offline nel Python DiffSinger verificato quando eSpeak manca nel processo principale; fonemizzazione contestuale francese con liaison e confini verificati; readiness EN/IT/FR effettiva; bundle completo con ID distinto |
| Zoom desktop | Controllo visibile sulla barra superiore, 50–200%, reset e Ctrl/Cmd +/−/0; sincronizzazione dopo bridge pronto, wrapper Windows/macOS/Linux e gestione degli errori |
| Zoom mobile | iOS/iPadOS Options e Android menu ⋮: scala dell’intera UI persistente, separata dallo zoom della timeline |
| Tipi progetto | Multitrack DAW + MIDI accetta audio e MIDI; MIDI soltanto MIDI; DAW/MTA8/MTA16 soltanto audio |
| Conversione | Comando esplicito in Setup e Info progetto, anteprima dei conteggi, conservazione inattiva delle tracce incompatibili e ripristino tornando a un tipo compatibile |
| Origine metronomo | Primo click effettivo incluso pre-roll = origine musicale, memorizzata nel progetto; Torna all’inizio raggiunge questa posizione |
| Transport | Auto basato sul BPM realmente noto, mm:ss.ms oppure Bar:Beats:Division:Ticks; tick a tre cifre, griglia unica per tempo fisso, zone e adattivo |
| Sincronizzazione | Corretto il doppio fattore di velocità dei click; metronomo audio/MIDI, VST, MIDI Clock, quantizzazione e conductor SMF coerenti |
| Quantizzazione | Comando visibile nell’editor MIDI, note selezionate, griglia musicale, intensità, swing e undo; tiene conto di origine, cambi BPM e offset della clip |
| Icone | Rimuovi = gomma, elimina tracce = righe con X, elimina intervallo = intervallo con X; Salva e Salva con nome hanno simboli distinti, conservando le etichette accessibili |

La conversione non trascrive o renderizza automaticamente il contenuto. Le tracce conservate mantengono clip, eventi MIDI, controller, strumenti e riferimenti ai media, protetti dalla pulizia e inclusi negli archivi portabili. Il server rifiuta import, autosave e job incompatibili prima delle elaborazioni costose. I progetti misti precedenti vengono migrati al tipo misto senza perdere MIDI. Un errore della conversione lascia invariato il progetto locale e sul server; i dati del server sono autorevoli per evitare che una cronologia vecchia perda tracce. Il limite preesistente di 1024 tracce per elenco viene verificato prima di convertire, senza lasciare un progetto non riapribile.

Il valore iniziale 120 è un segnaposto, non prova di un BPM calcolato o immesso. Auto usa la provenienza del tempo e conserva le scelte esplicite. Quattro divisioni per beat e 960 tick per quarto producono 240 tick per divisione nelle misure /4 e 120 nelle /8. L’origine sposta il riferimento musicale senza riscrivere i byte audio; le posizioni precedenti restano accessibili come misure zero/negative. Le zone mantengono numerazione globale e possono troncare una misura. Il pre-roll insufficiente estende non distruttivamente clip e metadata, incluse le tracce conservate.

L’import MIDI esterno allinea la clip all’origine; `align_origin=false` mantiene lo zero assoluto. L’export SMF0/1 segue per default il tempo udibile del WAV accelerato/rallentato; `time_domain=source` seleziona esplicitamente i tempi sorgente. I marker MTA di origine e rapporto consentono il reimport senza doppio offset o doppia variazione di velocità. I pattern SMF2 mantengono mappe indipendenti. La prova esterna con mido verifica che una nota a 1000 ms sorgente venga suonata a 500 ms con velocità 2× e torni a 1000 ms al reimport MTA. L’arrotondamento SMF del tempo intero in microsecondi è misurato: il nuovo test di riesportazione usa una tolleranza di 0,01 ms, senza modificare il benchmark di accuratezza neurale.

### Qixuan: esecuzione reale e pacchetto

**12/12 inferenze CPU ONNX effettive**, acustico e vocoder originali, 32 passi, **426,458 s** totali nell’ambiente disponibile. Tutti gli audio sono finiti e non silenziosi, mono 48 kHz PCM24, durata entro 25 ms dalla partitura. I casi comprendono IT testo/palatali/melisma, FR testo/nasali-arrotondate/melisma, EN, vocalizzo e quattro casi francesi di contesto. `les amis`, `un ami`, `vous avez` e `les haricots` hanno superato le verifiche specifiche. Il processo principale non aveva eSpeak: è stato esercitato davvero il nuovo percorso nel runtime separato, senza fixture sostitutive. Ulteriori 78 parole reali G2P non hanno prodotto fonemi sconosciuti; readiness effettiva EN/IT/FR riuscita.

Nuova banca: **MTA-Qixuan-2.7.0-IT-EN-FR-context-r210-final-bundle.zip**, **474.466.435 byte**.

SHA-256: `9ddc578cc4df3997d9a6725cdfeef6966ff51eeb9ca657d42ec78d22c85ee64f`.

CRC completo, inventario SHA/dimensioni, corrispondenza dei sorgenti motore, tutti i membri precedenti e **37 originali byte-identici** verificati. ID distinto `qixuan-2-7-onnx-it-en-fr-context-r210`; la banca precedente non viene eliminata. Il nuovo bundle resta disabilitato fino alla vera revisione/attivazione dell’operatore, conservando condizioni e avvisi originali. **IT/FR restano proiezioni EN/JA/ZH**, non un addestramento nativo: pronuncia, accento e qualità artistica richiedono ascolto. Nessun peso o diritto d’uso viene modificato.

WAV, richieste, log, SHA e attribuzioni sono in `validation/qixuan-itfr-context-final-audio/`. L’audit e la ricetta effettiva sono nei file `validation/r210-qixuan-completion-*`. Il cumulativo sorgenti non incorpora venv, cache o nuovi checkpoint; il bundle Qixuan è separato.

### Test conclusivi

**Regressione generale completa: 4,717 passed, 18 failed, 0 errors, 98 skipped, 6 warning, 1935.07 s. Tutti i 18 casi falliti sono stati corretti e rieseguiti con esito positivo sul codice finale: 4,735 casi distinti verificati complessivamente, oltre ai test saltati.** Non si tratta di una singola esecuzione generale tutta verde. Log/JUnit completi: `validation/r210-qixuan-midi-native-general.*`; riesame finale: `validation/r210-qixuan-midi-native-resolved.*`. Le modifiche tardive alla quantizzazione delle zone parziali, al tasto Invio del BPM, ai due comandi nativo/server di ritorno all’origine, alla mappa restituita dall’API adattiva e ai manuali HTML hanno verifiche mirate separate. Ruff sui sorgenti Python nuovi/modificati, compilazione Python, sintassi JavaScript e build C++ Release del core superati; il core condiviso dei test viene compilato una sola volta per sessione e copiato in percorsi privati per ogni modulo, mantenendo lo stato nativo isolato; le build indipendenti Docker/sorgenti restano separate; `pip check` del runtime generale e Qixuan puliti.

Selezioni mirate: zoom 39 passed; tipi di progetto + quantizzazione 20 passed; Qixuan 74 passed/3 skipped; clock 14 nuovi test passed; clock esteso 46 passed/2 skipped/5 esclusi. **I conteggi si sovrappongono e non si sommano.** La regressione iniziale interrotta e i diagnostici sono etichettati come tali: due contratti statici assumevano ancora soltanto i vecchi tipi e sono stati aggiornati, con 27 test mirati passati. Ulteriori fixture sono state aggiornate con i campi dei progetti reali, conservando le asserzioni su rollback, symlink e replay HTTP409. I permessi eseguibili persi durante l’estrazione sono stati ripristinati dai metadati originali, con sei prove mirate riuscite. Gli skip facoltativi G2P nel processo principale non vengono trasformati in pass: le inferenze separate provano il percorso reale. Ragioni esatte di tutti gli skip nel riepilogo JSON.

Il controllo Ruff esteso all’intero archivio segnala 51 rilievi in file tutti byte-identici al cumulativo iniziale; il confronto è documentato in `validation/r210-qixuan-midi-native-global-lint-baseline.json`. Non sono presentati come un controllo globale pulito. Il controllo dei sorgenti nuovi/modificati è pulito.

I tre timeout iniziali erano: compilazione ABI oltre 45 s, polling degli stem oltre 10 s e import oltre 5 s. Sono stati estesi soltanto i limiti dei test (compilazione 120 s e polling bounded più lungo), conservando l’esecuzione del binario entro 15 s e tutte le asserzioni. Le altre correzioni coprono fixture, struttura HTML, harness JavaScript e comportamento effettivo dei due comandi di ritorno all’origine e della mappa restituita dall’API adattiva.

Il download del sorgente pywebview per sola ispezione è stato rifiutato dal revisore automatico richiamando il vecchio vincolo sulle dipendenze. Non è stato ripetuto né aggirato; la correzione dello zoom è stata realizzata sui sorgenti e sulle interfacce disponibili. Il blocco non ha impedito lo sviluppo software qui consegnato.

### Collaudi sul target

Restano da eseguire sulle installazioni effettive: controllo grafico e scorciatoie Windows/macOS/Linux con il relativo motore WebView, build e dispositivi iOS/Android (SDK/compilatori assenti qui), driver audio/MIDI, clock hardware, VST/VSTi e ascolto Qixuan. I test con oggetti backend controllati non sono presentati come esecuzioni su Windows/macOS/mobile. Le prove di griglia usano dati ritmici controllati per isolare la sincronizzazione e non certificano l’accuratezza del rilevamento automatico dei beat.

Guide dettagliate: [Qixuan](R210_QIXUAN_IT_FR_CLOSURE_IT_EN.md), [tipi progetto](PROJECT_TYPES_R210_IT_EN.md), [origine e transport](MUSICAL_ORIGIN_TRANSPORT_R210_IT_EN.md), [zoom nativo](NATIVE_UI_ZOOM_R210.md). Manuali HTML IT/EN aggiornati. Lo SHA del cumulativo sorgenti è nel file `.sha256` e nell’audit esterno, evitando un digest autoreferenziale dentro lo ZIP. Tutti i percorsi del precedente cumulativo sono mantenuti, con SDK/legacy e metadati eseguibili preservati.

Il messaggio di commit è compatto, su una riga e cumulativo rispetto al lavoro noto dall’ultimo commit comunicato; lo SHA esatto di quel commit non è disponibile nell’archivio e non viene inventato. Nessun commit è stato eseguito.

## English

The requested software work is complete for the existing Qixuan bank and the native UI/MIDI workflow. **No native Italian/French acoustic training is claimed**: the disclosed EN/JA/ZH projection still requires linguistic and artistic listening. Twelve actual parent-process→pinned external G2P runtime→CPU ONNX acoustic/vocoder cases passed at 32 steps, including French liaison/aspirated-h checks, plus 78 actual G2P words and EN/IT/FR readiness. All waveforms were finite, non-silent, mono 48 kHz PCM24 and within 25 ms of score. The separate 474,466,435-byte complete bank has SHA-256 `9ddc578cc4df3997d9a6725cdfeef6966ff51eeb9ca657d42ec78d22c85ee64f`; all 37 original bank/vocoder members remain byte-identical. License admission remains genuine; the asset is disabled by default.

Desktop whole-interface zoom is visible in the top bar, separate from timeline zoom, with persistent 50–200% scale, reset and Ctrl/Cmd shortcuts, deferred bridge synchronization and error recovery. iOS/iPadOS and Android expose persistent whole-interface zoom in their native menus. Physical desktop/mobile GUI and device builds are not certified by headless tests.

New modes are mixed **Multitrack DAW + MIDI** and MIDI-only **MIDI**; other types remain audio-only. Explicit reversible conversion preserves incompatible tracks inactive, including MIDI events/plugins/media, portable archives and cleanup protection. Server-side guards reject incompatible operations before expensive jobs. Failed conversion preserves local state and authoritative server content.

One persisted musical origin includes the first metronome pre-roll click. Auto display distinguishes a known tempo from the initial 120 placeholder; alternatives are mm:ss.ms and **Bar:Beats:Division:Ticks** with three-digit ticks. Fixed/zonal/adaptive tempo, MIDI/VST clock, quantization and generated clicks share consistent source-time math. Double speed scaling is fixed. SMF0/1 export defaults to audible project timing, with explicit source-time option and safe own-file reimport. MIDI-only projects use MIDI metronomes. Quantization is visible, selected-note based, undoable, strength/swing aware and handles clip offsets. Five previously ambiguous toolbar icons are now distinct.

Complete general regression: **4,717 passed, 18 failed, 0 errors, 98 skipped, 6 warnings, 1935.07s**. All 18 failed cases were corrected and passed together on final sources: **4,735 distinct cases verified** across the full run and final retry. This is not a single all-green full invocation. Late quantization, BPM Enter and HTML manual changes have separate focused checks. Focused counts overlap; exact skip reasons, source changes, actual audio and audit evidence are included. Ruff for changed/new Python sources, compilation, Node syntax, native core Release build and dependency consistency checks passed. Whole-archive Ruff reports 51 baseline findings, all in files byte-identical to the input archive; a clean global lint is not claimed. Legacy AI, SDK and all previous archive paths are retained; no Git or production operations occurred. The historical 10–16-instrument Audio-to-MIDI accuracy gate remains unresolved and is not relabeled as hardware-only work.
