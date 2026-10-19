# Live VST3 checkpoint - 0.3.0-r210

> Server aggiornato / Server update: [SERVER_VST3_R210.md](SERVER_VST3_R210.md). Il server ora include runtime VST3, catalogo, controlli web e streaming live al browser. Le descrizioni sottostanti documentano il checkpoint nativo precedente.

## IT

Questo checkpoint sostituisce le precedenti dichiarazioni che l'hosting live non fosse implementato. L'opzione C++ mantiene il dispositivo nativo e ora usa un worker persistente per gli effetti audio VST3 di tracce e master. Il motore corrente resta disponibile. Il backend live e' Pedalboard/JUCE, con filtri interni PyAV e mixer C++; non e' il vecchio probe sperimentale Steinberg e non esegue plugin nella callback hardware.

Sono implementati parametri live, istanze persistenti, ordine misto degli insert, gain/fader/pan/mute/solo, bypass master, fade master, tempo/pitch, clock/seek/pausa/fine, editor della stessa istanza e acquisizione dello stato prima dello stop. Seek e modifiche ai filtri reinizializzano le memorie DSP; gli insert aggiunti o rimossi possono richiedere una pausa di caricamento. Il ring buffer del dispositivo rimane allocato prima della riproduzione e non esegue Python, I/O, plugin o attese nella callback. L'IPC a file e tutto il processing plugin rimangono fuori dalla callback.

Le sorgenti dry e i clip vengono preparati prima della riproduzione; gli effetti VST3 non vengono prerenderizzati. Il buffer nominale live e' di tre blocchi da 512 campioni; non rappresenta la latenza end-to-end garantita. Underrun, uscita anomala, blocco del worker e PCM non valido vengono rilevati. Un worker bloccato viene terminato con attese limitate. Nessuna sostituzione silenziosa con audio dry.

Limiti espliciti: effetti audio mono/stereo, massimo 64 tracce, nessun VSTi/MIDI o sidechain esterno, uscita di sistema predefinita, coda finale limitata a 2 secondi e lookahead senza output limitato a 960.000 campioni. Non e' un sistema per registrazione o monitoring di ingresso ASIO.

Il plugin reale usato nelle prove e' CHOWTapeModel dal repository ufficiale dei test Pedalboard, commit 05e8f0b3c4851e77485d7e842dc0355b44106471, SHA-256 del modulo Linux 7f875a6922ca9e49c7a742a27f26152c685bed2991460781640cc23cfb16d319. Il binario non viene incluso nel package. La CI scarica e verifica il modulo prima della suite e usa Xvfb per la finestra originale. La prova locale della finestra originale e' passata su Xvfb/Openbox, incluse riproduzione, seek e parametri sulla stessa istanza; le query X11 BadWindow sul solo XID nullo sono gestite senza terminare il worker, gli altri errori vengono inoltrati. Qui il dispositivo null e' usato esplicitamente per le prove compilate; il backend di produzione rifiuta il fallback null. Non sono state eseguite prove di ascolto su Windows/macOS. I PDF IT/EN sono aggiornati sotto app/docs; questa nota e i risultati in validation distinguono prove svolte e prove predisposte per CI.

## EN

This checkpoint supersedes earlier statements that live hosting was unimplemented. Selecting C++ enables persistent live VST3 audio-effect processing on tracks and master, using Pedalboard/JUCE, PyAV built-in filters and C++ mixing/device output. The Current engine remains available. This is separate from the old experimental Steinberg probe and does not call plugins inside the hardware callback.

Implemented paths include live parameters, persistent instances, mixed insert order, input gain, faders/pan/mute/solo, master bypass and fades, tempo/pitch, native clock/seek/pause/completion, the same-instance original editor and state capture before stopping. Seek resets DSP memory; adding/removing plugins may pause for loading. Dry clip sources are prepared before playback, while VST3 effects are processed during playback. The fixed device ring and callback contain no Python, I/O, plugin calls or waits. File IPC and effect processing run outside the callback.

The normal output queue is three 512-sample blocks, not a guarantee of total latency. Worker exits, hangs, invalid PCM and underruns are detected. Shutdown is bounded and processing failures never silently bypass an effect.

Scope: mono/stereo audio effects, up to 64 tracks, default system output, VST instruments/MIDI (see VSTI_MIDI_R210.md); no external sidechains, dedicated ASIO input monitoring or recording. Playback tails are bounded to 2 seconds and lookahead without output to 960,000 samples. Windows/macOS listening acceptance remains outstanding.

The real Linux CHOWTapeModel test module is fetched from the official Pedalboard test repository with the commit and SHA-256 above and is not shipped. CI uses Xvfb for the original editor test. The original-editor test passed locally under Xvfb/Openbox, including playback, seek and parameters on the same instance. A narrow X11 handler suppresses BadWindow for the zero-window sentinel only; all other errors are forwarded. Local compiled device tests explicitly use the null backend; production rejects silent null fallback. Updated IT/EN manuals are shipped under app/docs; validation records the exact local results and environment exclusions.

## Server DSP / DSP server

C++ DSP is available in server mode as well as native mode. Admin Settings > Web App selects current/C++ globally for new previews, bounces and exports. `server-audio-engine.json` is separate from native preferences. Engine snapshots preserve in-flight jobs and cache identities distinguish renderers. Admin GET/PUT `/api/admin/audio-engine` enforces authentication, admin role and CSRF on writes. Missing ABI-compatible libraries prevent selecting C++; they never silently change an existing C++ render to the current engine. Server status reports browser playback and never a physical native device.

RPM/DEB staging compiles on the target distribution/architecture, validates ABI 1 using standard-library ctypes and packages `bin/libmta_audio_core.so`; the offline proof binds its hash and extracted-payload smoke loads it. Docker uses a matching Debian builder stage. No sound device or GPU is required for the DSP. Native live VST3 and hardware output remain separate capabilities. Local tests cover real server renders and selection/security; the distribution matrix and deployment on the actual server still need to run after commit.
