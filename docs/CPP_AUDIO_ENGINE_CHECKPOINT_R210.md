> Aggiornamento / Update: [LIVE_VST3_HOST_R210.md](LIVE_VST3_HOST_R210.md). Le limitazioni live descritte nei checkpoint precedenti sono storiche.

> Stato aggiornato / Updated state: [SUBSCRIPTION_ONLY_CREDITS_DEVICE_R210.md](SUBSCRIPTION_ONLY_CREDITS_DEVICE_R210.md). Le descrizioni precedenti sono storiche.

# Motore C++ opzionale · checkpoint 0.3.0-r210

## Stato attuale — IT

Questa fase collega **realmente** DSP compilato ai render delle app native. Il motore corrente resta il default. Nelle impostazioni native si può scegliere **Motore corrente** oppure **DSP C++ (sperimentale)**. Si può tornare al motore corrente in qualsiasi momento a riproduzione ferma. Il cambio vale per i nuovi render: un render già iniziato conserva il proprio motore fino alla fine. Non viene modificato il formato dei progetti.

Il selettore è nativo e locale all'istanza, salvato in `native-audio-engine.json` nella directory dati dell'app. Web/server ignorano questo file e continuano a usare il percorso corrente. La verifica di disponibilità legge ABI e un piccolo test DSP; non importa NumPy, SoundFile, PyTorch o altri stack pesanti per aprire le impostazioni. Non compila nulla all'avvio. Se il motore C++ selezionato non è disponibile, il render fallisce con un messaggio esplicito: il selettore consente di tornare al motore corrente.

### Percorso collegato

1. I clip vengono preparati dalla timeline esistente mediante FFmpeg, rispettando intervalli, spostamenti, delay negativo e sample rate.
2. Il gain di ingresso della traccia viene applicato dal C++ **prima** degli insert, compresi quelli non lineari.
3. Gli insert integrati e i VST3 offline conservano i percorsi esistenti.
4. Il C++ applica fader/pan lineare, mute/solo e somma stereo di massimo 64 tracce per render. Le tracce corte vengono completate con silenzio e la durata segue quella più lunga, anche in presenza di mute/solo.
5. Gli insert master elaborano la somma; il C++ applica poi volume e fade in/out master, con posizioni assolute dei campioni e senza applicazioni duplicate. Le tracce bounce post-master conservano il bypass del master.
6. FFmpeg conserva time-stretch/pitch, normalizzazione finale e codifica WAV/MP3/FLAC.

Il flusso è a blocchi di massimo 4096 frame e non carica l'intero brano in RAM. I kernel C++ non allocano, non fanno I/O e non usano lock. Gli adapter Python gestiscono file, memoria e controllo **fuori** da qualsiasi callback audio. PCM non finiti, overflow, parametri e alias non validi vengono rifiutati. Il C++ conserva headroom interna: non introduce clipping nascosto. I render C++ pubblicano il risultato con sostituzione atomica e conservano il file precedente se un passaggio fallisce.

La cache di preview include l'identità del motore sia nel backend sia nel frontend. Il cambio richiede playback fermo, invalida i buffer decodificati e non perde file o modifiche del progetto.

### Limiti intenzionali

**Il trasporto audio è ancora quello corrente.** Le impostazioni lo dichiarano. La normale timeline può riprodurre file direttamente o utilizzare WebAudio; selezionare DSP C++ non trasforma questo percorso in un callback nativo. Nessun dispositivo WASAPI/ASIO/CoreAudio/ALSA viene aperto da questa fase. Non è una certificazione di bassa latenza.

`native_transport_ready=false` e `native_host_ready=false` restano separati e obbligatori. L'hosting VST3 realtime, le finestre originali dei plugin, il collegamento live di MIDI/automazioni e la PDC dell'intero grafo restano aperti. Gli insert integrati, time-stretch, decoder/encoder e preparazione dei clip non sono stati riscritti in C++. Questo è un checkpoint di integrazione DSP, non la chiusura dell'intero motore nativo.

Il nuovo percorso può richiedere più passaggi FFmpeg del corrente: non viene promesso un miglioramento delle prestazioni prima dell'integrazione del trasporto e dell'ottimizzazione del grafo. I limiti di 64 tracce, la selezione sperimentale e l'assenza del trasporto nativo sono espliciti. Per progetti oltre tale limite si può utilizzare il motore corrente.

### Packaging e sviluppo

`python scripts/build_audio_core.py` compila e verifica la libreria per l'architettura corrente. Nella CI Windows/macOS il passo viene eseguito prima di PyInstaller e imposta `MTA_NATIVE_AUDIO_CORE` per includerla in `bin`. Linux già compilava il medesimo target e ora include anche i kernel di render. La selezione cerca sia `mta_audio_core.dll` sia il nome con prefisso `lib`, correggendo il rilevamento Windows.

Per una prova da sorgenti: compilare e impostare `MTA_AUDIO_CORE_PATH` al percorso completo della libreria prodotta, poi avviare l'app nativa. Non distribuire librerie compilate per un'altra architettura.

I build macOS segnalati fallivano durante la raccolta dei test, prima del launcher, tentando di creare `/data/projects`. `app/runtime_paths.py` ora condivide la scelta del percorso nativo tra storage, autenticazione e launcher quando manca `MTA_DATA_DIR`; il default server resta `/data/projects`. I passi di test Windows/macOS usano inoltre `${{ runner.temp }}/mta-native-project-tests` per dati, stato job e directory nativa. Non sono stati eseguiti build Apple/Windows reali in questo ambiente Linux.

### Verifica

I test includono CMake/C++ reale, ABI, errori atomici, buffer strided, gain, bilanciamento, headroom, blocchi irregolari, equivalenza dei render a 44.1/48/96 kHz, mono/stereo, solo/mute, delay, insert non lineari e master, fade più lunghi del progetto, BPM e bounce post-master. Il confronto senza time-stretch usa tolleranze PCM strette. Con WSOLA condiviso, piccoli arrotondamenti precedenti possono cambiare un punto di sovrapposizione: si verificano durata, errore RMS e picco del residuo, senza dichiarare identità bit per bit.

Le impostazioni non importano stack ML/audio pesanti. Un test subprocess vieta accessi a `/data` durante l'import pre-launch nativo. La regressione dei progetti nativi viene ripetuta con `MTA_DATA_DIR` assente. I risultati completi sono in `validation/r210-cpp-choice-*`.

### Prossimo checkpoint

- Integrare scheduler di timeline e grafo DSP nel runtime C++ persistente, evitando i render intermedi dove possibile.
- Implementare apertura/configurazione/chiusura dei dispositivi e trasporto nativo, attivabile esclusivamente con motore C++ selezionato e capacità effettivamente verificate.
- Collegare play/pause/seek/stop, clock, loop, fader, meter e riconfigurazioni al trasporto con pubblicazione atomica dei grafi.
- Verificare callback senza allocazioni, I/O o lock; underflow, recovery e latenze misurate su macOS/Windows/Linux.
- Integrare worker VST3, PDC dinamica, eventi, stato e GUI, poi eseguire la matrice di plugin reali.

Il reset del budget temporale della conversazione non è osservabile dall'app né dagli strumenti di sviluppo: non è presente una ripresa automatica legata alle 5 ore. Questo file e lo ZIP cumulativo sono il punto di ripartenza. La versione resta **0.3.0-r210**. Il package precedente è stato confermato committato dall'utente; questo ciclo non effettua commit, push, tag o release.

## English

This checkpoint introduces a persistent, native-only **Current engine / C++ DSP (experimental)** choice, defaulting to the current engine. The compiled DSP is actually used for input trim before inserts, stereo fader/balance/mute/solo summing of up to 64 tracks, and master gain/fades after master inserts. Existing timeline preparation, built-in/offline VST3 processing, time/pitch, normalization and encoding remain shared FFmpeg/Pedalboard paths. Post-master bounces avoid duplicate processing.

Rendering is bounded-memory, with 4096-frame kernels, full finite/overflow preflight, no hidden clipping and atomic final publication. A per-render context freezes the backend across nested calls; changing preferences affects subsequent renders only. Preview identities and decoded caches distinguish engines. An unavailable saved C++ selection causes an explicit error and can be reset to Current in Settings. Readiness probes do not load NumPy, SoundFile or ML libraries and never compile at startup.

The current browser/WebAudio transport remains active. **Native device transport and realtime VST3 hosting are not enabled.** `native_transport_ready=false` and `native_host_ready=false` remain explicit. Additional FFmpeg passes mean this checkpoint does not promise faster rendering. It is a working DSP integration milestone, not completion of the native engine.

Windows/macOS build steps compile and self-test the C++ runtime before freezing. Windows runtime discovery accepts prefixed and non-prefixed DLL names. Shared pre-launch data-root resolution and explicit runner-temporary directories fix macOS test collection trying to create `/data/projects`; server defaults remain unchanged.

Tests exercise actual compiled kernels, end-to-end audio, failure preservation, rates, channel layouts, timing, master effects/bypass, preferences and pre-launch imports. Real Apple/Windows builds, hardware transport, listening/latency acceptance and commercial VST3 qualification remain outstanding. The next steps are a persistent native timeline/graph, device transport gated by C++ selection, callback and recovery tests, then complete VST3 integration. No 5-hour usage-budget reset event is available to automatically resume work; this checkpoint and cumulative ZIP preserve the continuation state.

## Continuazione: timeline preparata C++ (IT / EN)

Aggiunta ABI separata `mta_timeline_abi=1`, con piani immutabili che copiano e validano fino a 100000 segmenti su 64 route. Ogni interrogazione usa una posizione assoluta in campioni: seek avanti/indietro, confini adiacenti, silenzi e offset di sorgente non dipendono da cursori condivisi. Sono rifiutati overlap sulla stessa route, coordinate fuori intervallo e capacità insufficiente senza scrivere risultati parziali. Creazione e distruzione allocano sul thread di controllo; la query C++ non alloca, non apre file e non acquisisce lock. La durata del piano deve coprire tutte le query in corso.

Il mixer offline C++ usa effettivamente il piano preparato per decidere quali porzioni leggere dalle sorgenti stereo già preparate. La conversione dei clip originali e gli insert rimangono nei percorsi condivisi FFmpeg/Pedalboard; non viene ancora eliminato il passaggio di preparazione su file. Il wrapper Python non è adatto a una callback real time. Il motore corrente resta il default e il trasporto resta WebAudio. **Dispositivi audio e host VST3 live non sono ancora abilitati**. Nuova identità preview `cpp-render-dsp-timeline-2` per evitare cache obsolete. Un runtime con il solo DSP precedente non viene dichiarato disponibile per questa integrazione.

Prepared immutable native plans now copy and validate up to 100000 clips over 64 routes. Queries use absolute sample coordinates, support arbitrary seeks and source offsets, and reject same-route overlaps, overflow and insufficient output capacity atomically. Control-side creation/destruction allocate; the C++ query performs no allocation, I/O or locking. The offline C++ mixer now uses these plans to schedule reads from prepared stereo sources. Original clip decoding and inserts remain shared FFmpeg/Pedalboard stages; device transport and live VST3 hosting remain disabled, with Current as the default. The Python adapter is offline/control code, not a realtime callback. Next steps: decoded clip streams and prepared DSP graphs, lifetime-safe graph swaps, device I/O, clock/loop/meters, then realtime VST3 and hardware acceptance.

Verifica: `tests/test_r210_cpp_timeline.py` confronta 500 query casuali riproducibili con un riferimento indipendente; verifica seek, copie dei descrittori, bordi, overlap, overflow e fallimenti atomici. I render completi del checkpoint precedente restano nella regressione. Risultati: `validation/r210-credit-timeline-*`.
