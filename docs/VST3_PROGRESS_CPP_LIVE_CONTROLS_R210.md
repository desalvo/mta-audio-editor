# r210 — installazione VST3 e controlli live C++ / VST3 installation and C++ live controls

## Italiano

Versione invariata: **0.3.0-r210**. Baseline: `MTA-0.3.0-r210-ci-sdk-midi-progress-cumulative.zip` (SHA-256 `cb86ddbcc58996f8990e2df7f4c1e295c170a12a1dc81a4042549e781ffed8fb`). Sono conservati tutti i file e gli sviluppi precedenti, comprese le correzioni CI SDK/MIDI.

### Installazione dei plugin opzionali

Ogni scheda del catalogo mostra **Non installato**, **In attesa di installazione**, **Installazione in corso**, **Installato** oppure **Installazione fallita**. La barra appare solo sulla scheda del plugin attualmente elaborato e scompare subito alla sua conclusione, anche quando altri plugin sono ancora in attesa o in compilazione. Fase, attività del tool e tempo trascorso descrivono l'avanzamento reale. La barra è indeterminata: download, compilatori e dipendenze non forniscono una percentuale totale affidabile.

Il server pubblica gli esiti progressivamente; un errore non impedisce di elaborare i plugin successivi. Gli esiti finali vengono conservati accanto ai log di compilazione e ricompaiono riaprendo il catalogo anche dopo un riavvio. Riaprendo il catalogo durante un job nello stesso processo server si riprende il monitoraggio. Una perdita temporanea di connessione provoca nuovi tentativi senza simulare il completamento. Autorizzazioni admin, consenso licenze e revisioni sorgenti bloccate restano richiesti.

### Trasporto e mixer C++

- Spazio richiama lo stesso comando Play/Pausa del pulsante di trasporto, comprese le implementazioni C++ web e native. Rimangono esclusi i campi di testo e le ripetizioni automatiche del tasto.
- Il grafo misura RMS stereo e picchi per canale dopo insert, volume, pan, mute/solo; il master è misurato dopo l'elaborazione finale, incluso il routing di bypass. Le misure provengono dai campioni elaborati, senza stimarle dalla waveform. Il frontend browser mostra i livelli del blocco in ascolto, azzerandoli in pausa o in assenza di audio; rimane il latch di clipping a 0 dBFS.
- Volume, gain, pan, mute, solo e volume master vengono inviati al grafo mediante controlli live limitati e validati, senza attendere un salvataggio del progetto. Autosave e salvataggio esplicito mantengono le normali responsabilità di persistenza. Non vengono accettati percorsi, sorgenti o plugin attraverso questa API.
- Aggiornamenti aggregati con cadenza breve anche durante il trascinamento, invece di attendere il rilascio. Parametri e catene FX continuano a seguire il percorso di aggiornamento degli insert; la sessione e gli stati VST3 vengono preservati.
- Blocchi browser iniziali da 4.096 frame e coda contenuta, adattabili ai tempi effettivi delle richieste sulle connessioni lente. Nessun seek o reset del plugin per muovere un fader. La latenza residua dipende da rete, coda, elaborazione e dispositivo audio.
- Nel trasporto nativo un breve stato `preparing` del bridge durante un aggiornamento non viene interpretato come guasto. Modifiche ai fader in pausa non impongono una preparazione integrale alla ripresa.

### Verifica e limiti

Esito finale: **4173 test passati, 35 saltati, 10 esclusi per socket/agente non disponibili**, zero fallimenti. Suite mirata con CHOW Tape: **57 passati, uno saltato senza display**. Nove nuove regressioni passate; altri 44 controlli legacy e i controlli Ruff/Bandit/licenze/sintassi/pip check passati.

Rapporti JUnit e JSON sono in `validation/r210-live-mixer-*`, `validation/r210-native-live-controls.xml`, `validation/r210-cpp-live-controls-browser.json` e `validation/r210-current-engine-regression-browser.json`. Lo script `scripts/validate_cpp_live_controls.py --core /percorso/libmta_audio_core.so` ripete l'accettazione su dati temporanei: server ASGI, sessione autenticata, Chromium, WebAudio e DSP C++ reali.

Prima prova C++ su otto tracce: avvio 0,902 s; volume applicato al flusso udibile in circa 0,235 s; pausa/ripresa da Spazio, posizione ferma in pausa, VU master/canali, pan e aggiornamenti durante il trascinamento passati. Motore originario: avvio 1,598 s e riavvio cache 0,185 s, senza render backend aggiuntivi o errori JS, con bozza dell'editor plugin preservata. Sono misure locali ripetibili, non garanzie di latenza su Internet.

La suite mirata usa anche il plugin di prova CHOW Tape del CI, scaricato fuori dal progetto dalla sorgente bloccata e verificato SHA-256; nessun binario del plugin viene incluso nel cumulativo. Una prima prova con ADelay non era adatta alle asserzioni di uscita immediatamente non silenziosa della fixture: le accettazioni finali usano la fixture prevista dal CI, senza modificare le soglie o disattivare test.

Restano da verificare sull'installazione reale Rocky/HAProxy e sui dispositivi audio Windows/macOS: risposta percepita, VU, Spazio e installazione con i toolchain effettivi. Nessuna modifica a produzione, commit, push, tag o release eseguita.

## English

Version remains **0.3.0-r210**. All earlier development and standalone SDK/editor isolation fixes are retained.

Each optional-plugin card now has its own installation state, live build activity and indeterminate progress bar. The bar disappears as soon as that plugin finishes. Results are published incrementally, final failures survive a catalog reopen/server restart, and reopening during an active in-process job resumes monitoring. Transient connection failures retry. Administrator authorization, reviewed pinned sources and explicit license consent remain mandatory.

Space uses the shared Play/Pause command across all engines. C++ graphs provide measured post-channel RMS/peaks and final master levels; browser meters follow the audible PCM chunk and clear on pause. Small validated mixer updates no longer depend on saving the full project. Continuous gestures are throttled rather than delayed until release; pan is explicitly included. Normal project persistence remains with Save/autosave. No source paths or plugin code are accepted by the mixer endpoint.

The browser starts with 4,096-frame chunks and a short queue, adapting to measured round-trip times on slower links. Faders do not seek or reset plugins. The native bridge tolerates temporary preparation status during updates. Existing source, PCM sequence, session ownership and CSRF checks remain enforced.

Real local ASGI/Chromium/WebAudio/C++ acceptance on eight tracks measured 0.902 s startup and 0.235 s from fader change to the audible meter response. Play/Pause, a stationary paused cursor, track/master meters, pan and continuous gestures passed. The original engine also passed with 1.598 s startup and 0.185 s cached restart; plugin-editor drafts were preserved. These are local observations, not Internet latency guarantees. Reports and repeatable probe commands are listed above. Final full regression: **4173 passed, 35 skipped, 10 excluded for unavailable host-agent sockets**, no failures. The real-plugin targeted suite passed 57 tests (one display-dependent skip), and all nine new regressions passed. Physical Windows/macOS audio devices and the production Rocky/HAProxy deployment still require acceptance; no production changes or Git publication were performed.
