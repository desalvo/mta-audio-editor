> Aggiornamento / Current implementation: vedere / see VST3_COMPLETION_R210.md. Le limitazioni dei checkpoint riportati sotto sono superate ove indicato nel documento aggiornato.

# VST3 server - 0.3.0-r210

## IT - Attivazione

1. Costruire e installare il package server aggiornato. RPM/DEB includono nel wheelhouse offline Pedalboard, PyAV e Mido; Docker li installa con le dipendenze base. Il DSP C++ viene compilato per l'OS/architettura di destinazione. Nessuna compilazione avviene all'avvio.
2. Installare effetti VST3 Linux compatibili con CPU, librerie e licenza del server in `/opt/mta/vst3` (creata dai package), `/usr/lib/vst3` o `/usr/local/lib/vst3`. Non copiare plugin Windows/macOS. Per percorsi aggiuntivi impostare `MTA_VST3_PATHS` nell'ambiente del servizio; separare con `:`. Le directory non devono essere scrivibili da gruppo/altri utenti, ne' essere interne a `MTA_DATA_DIR`. Non e' previsto l'upload di eseguibili da utenti web.
3. In Docker montare i plugin, per esempio con `-v /srv/mta-vst3:/opt/mta/vst3:ro`. Per systemd, dopo modifiche all'ambiente riavviare il servizio. MTA non scarica o redistribuisce plugin di terzi; installazione e licenze sono responsabilita' dell'amministratore.
4. In Impostazioni > Web App controllare disponibilita' DSP/runtime, numero di plugin e scegliere C++. Il link al manuale PDF usa la lingua corrente. Gli utenti possono quindi aggiungere VST3 da Insert su tracce e master e modificarne i parametri dal browser.
5. Con almeno un VST3 attivo, Play usa il worker server live e l'audio del browser. Il motore corrente mantiene il percorso offline. Gli export/bounce usano il progetto salvato. Le finestre grafiche native dei plugin non vengono trasmesse: si usa l'interfaccia web dei parametri.

## Architettura e limiti

Il worker mantiene il grafo C++/Pedalboard-JUCE/PyAV gia' condiviso con il percorso nativo. Le sorgenti dry vengono preparate nel worker, insieme ai suoi sottoprocessi FFmpeg, dentro un process group terminabile. Il processo web non carica i binari dei plugin. Non si tratta di una sandbox di sicurezza per eseguibili non fidati: i plugin devono essere installati dall'amministratore.

L'API richiede identita' autenticata, accesso al progetto e proprieta' della sessione. Le scritture usano la protezione CSRF esistente. Le sequenze PCM impediscono replay/duplicazioni; ogni blocco e' al massimo 32768 frame stereo float32 little-endian. Il browser accoda un quantitativo limitato di audio, senza scaricare un intero render. L'orologio segue i buffer realmente riprodotti; pause/seek attendono i pull in corso prima di azzerare la sequenza. Dati non finiti, mismatch, crash e timeout interrompono il live, senza fallback dry.

La creazione risponde subito con HTTP 202 e uno stato `preparing`. Il browser interroga lo stato fino a `ready` o `failed`; puo' cancellare anche durante la preparazione. I timeout del reverse proxy non devono coprire l'intera inizializzazione. La capacita' globale conta anche le sessioni in preparazione.

Sono supportati effetti audio mono/stereo, massimo 64 tracce e le catene gia' previste dal mixer. Parametri, gain, fader, pan, mute/solo, insert master, bypass master e fade condividono lo stesso grafo. Sono inclusi strumenti VSTi e tracce MIDI persistenti: vedere VSTI_MIDI_R210.md. Il monitoring MIDI/VSTi usa un bus WebSocket separato; resta escluso l'input monitoring audio e il sidechain esterno. La coda finale e' limitata a 2 secondi; il lookahead senza output e' limitato a 960000 campioni. La latenza di rete/buffering rende il percorso adatto all'ascolto dell'editor, non al monitoring di ingresso.

## Risorse e manutenzione

- `MTA_SERVER_VST3_MAX_SESSIONS`: default 8, intervallo 1-64; massimo 2 per utente, una per identita' browser. Una nuova sessione sostituisce quella dello stesso browser/utente.
- `MTA_SERVER_VST3_START_TIMEOUT`: default 120 secondi, intervallo 10-900. Include preparazione e caricamento plugin.
- `MTA_SERVER_VST3_DRY_LIMIT_BYTES`: default 4 GiB; intervallo 16 MiB-64 GiB. Limita i dati dry della sessione e la dimensione dei singoli file nel worker POSIX. I dati vengono eliminati alla chiusura.
- Nessun pull significa nessuna elaborazione audio anticipata. Il browser invia heartbeat anche in pausa. Dopo 60 secondi senza richieste la sessione viene terminata e ripulita; crash del browser e reload non lasciano worker permanenti. Arrestare il servizio chiude le sessioni nel lifespan.
- I limiti della coda AI e il suo accounting non vengono riutilizzati per questi normali effetti DSP: non sono inferenze AI. Nessuna misura o voce di billing AI viene fabbricata per il VST3.

## EN - Setup and behaviour

Install the updated server package: the RPM/DEB offline wheelhouse and Docker include Pedalboard/PyAV/Mido; the C++ DSP is built for the target OS/CPU. Install trusted Linux audio effects in `/opt/mta/vst3`, `/usr/lib/vst3`, `/usr/local/lib/vst3`, or additional colon-separated `MTA_VST3_PATHS` roots. Roots must be outside project storage and not group/world writable. Mount Docker plugin directories read-only. Plugins are not bundled or uploaded by web users, and their licenses must permit the intended use.

Select C++ in admin Settings > Web App, then add track/master effects in the mixer and use the web parameter controls. Active VST3 inserts enable persistent server processing during browser playback. Offline export/bounce remain available with either engine. The original graphical plugin editor remains a desktop capability. Saved parameters are reused when reopening and exporting projects.

Each browser/user has an authenticated, project-scoped worker. The web process never loads plugins; the child owns dry-source preparation and the shared C++/Pedalboard/PyAV graph. A private process group allows killing the worker and its FFmpeg children. This is process isolation for trusted administrator-installed code, not a security sandbox for arbitrary executables.

Creation returns HTTP 202 immediately with a `preparing` state. The browser polls until ready/failed and may cancel during initialization. Capacity includes preparing sessions, and reverse proxies need not hold a long initialization request open.

PCM is pulled in bounded, sequenced chunks, with finite sample/size checks, no caching and no automatic dry fallback. Pause/resume/seek coordinate outstanding requests before resetting the DSP sequence. The cursor follows audible buffers, including gaps caused by slow networks. Normal queued audio can reach about 1.4 seconds plus network/device/effect latency; this is not low-latency input monitoring. A stalled or crashed user worker does not stop another user's worker.

Defaults: 8 global sessions (1-64 configurable), 2 per user, 120-second initialization timeout (10-900), 4 GiB prepared-audio limit (16 MiB-64 GiB), 60-second idle expiry and a 2-second playback tail. Native device output remains separate. Mono/stereo audio effects and MIDI/VST instruments share a maximum of 64 tracks. See VSTI_MIDI_R210.md for import, piano roll, instrument selection and MIDI limitations. External sidechains remain unsupported. VST3 effects do not fabricate AI billing/accounting entries.

## Validation

Targeted tests use the real, hash-pinned upstream CHOWTapeModel effect without bundling it. They cover server discovery/inspection, PCM, seek, parameter updates, saved-project exports, ownership/CSRF, capacity/expiry, failed sequence handling, worker stalls and concurrent-user fault isolation. The shipped JavaScript is exercised with Node; the optional Playwright test uses a real Chromium, HTTP server, WebAudio and real plugin worker, without mocking those layers. Reports are under `validation/r210-server-vst3-*`. CI provisions Playwright/Chromium and the pinned plugin. Actual RPM/EL10, production proxy/network and user plugin acceptance remain separate deployment checks.


## Runtime host e monitoring MIDI / MIDI monitoring and host runtime

Il packaging compila Pedalboard 0.9.26+mta1 dal commit upstream fissato da scripts/patch_vst3_runtime.py. La piccola estensione native/host_transport/MtaHostTransport.h e gli script di ricostruzione sono distribuiti nel sorgente MTA; le sorgenti vendor restano nella cache di build. Docker usa uno stage dedicato; RPM/DEB includono il wheel personalizzato nel wheelhouse hash-locked. Gli smoke test di installazione richiedono l'ABI _mta_set_transport. Non sostituire il wheel con la versione stock se si desidera il tempo host. Vedere docs/MIDI_LIVE_HOST_R210.md per ricostruzione e prove.

The /api/projects/{pid}/midi-monitor/{tid} WebSocket requires an authenticated project owner and matching Origin/Host. Monitoring shares normal VST session capacity/expiry, including preparation, and uses bounded 1024-frame stereo replies, sequence validation and bounded MIDI messages. Reverse proxies must forward WebSocket Upgrade and preserve Host/Origin. No server ALSA/MIDI hardware access is required. Browser MIDI output targets the user's own ports. Windows/macOS devices and the actual HAProxy deployment still require listening/connection acceptance.
