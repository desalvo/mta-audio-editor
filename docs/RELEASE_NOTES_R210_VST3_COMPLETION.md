# MTA Audio Editor 0.3.0-r210 - VST3 server editor and shared audio/MIDI

## IT

- Editor originale del plugin anche sul server, sulla stessa istanza live o di monitoring VSTi: immagini, mouse, tastiera, chiusura, stato persistito, controllo accessi/CSRF e conflitti. Display privato autenticato, credenziali eliminate prima dell’avvio del worker e confinamento filesystem Linux Landlock richiesto per la GUI.
- Xvfb privato compilato durante il packaging RPM/DEB da sorgente X.Org 21.1.24 con checksum bloccato, licenza e manifest. Non richiede un package Xvfb mancante su EL10, né repository terzi. Il binario installato non conserva percorsi RPATH della build. Docker usa il package della distribuzione.
- PPQ continuo per mappe del metronomo a zone e adattive, misura, inizio battuta e suddivisione dei blocchi ai cambi di tempo; MIDI Clock coerente con la mappa.
- Sidechain esterna per gli insert con bus ausiliari: traccia sorgente pre-insert, bus e gain. Stesso grafo C++ per live, bounce ed export.
- SysEx conservati negli SMF, consenso esplicito per hardware, nessun replay al seek; zone/canali/RPN MPE; UMP nativo tramite libremidi, registrazione e archivio JSON senza perdita, eventi VST3 mappati a piena risoluzione del protocollo e rifiuto esplicito dei tipi senza mapping.
- Registrazione audio esterno: dispositivo locale, compensazione latenza, Play opzionale, ring C++ nativo o AudioWorklet web, upload limitato con sequenze e quote e pubblicazione transazionale. Conferma solo dopo il salvataggio della traccia; chiusura protetta e recupero della parte ricevuta in caso di errore di rete. Permesso microfono limitato all’editor della stessa origine e consenso del browser; descrizione autorizzativa macOS IT/EN.
- Regressione: il test dei job stem attende anche la ricevuta terminale della coda prima di ripristinare i fixture, evitando interferenze con i test AI successivi.
- Manuali VST3 IT/EN aggiornati e controllati visivamente. Motore corrente ancora selezionabile; revisione invariata e intero archivio cumulativo precedente preservato.

Esiti eseguiti: validation/r210-vst3-completion-result.json. Le prove di GUI in questo ambiente usano una modalità esplicita di test perché Landlock e socket Unix non sono disponibili; non equivale alla certificazione del confinamento sul server reale. Restano le prove EL10/LXC/HAProxy, dispositivi fisici, endpoint UMP/driver, latenza e plugin dell’utente. ASIO dedicato e SMF2/SMPTE restano fuori ambito. Nessun commit, push, tag, release o intervento sul server di produzione.

## EN

Add authentic server plugin editors on the active playback/monitoring instance, persistent state, authorization/CSRF/conflict checks, private authenticated displays and filesystem confinement. Scrub credentials before worker exec. Bundle a SHA-pinned, target-built Xvfb in RPM/DEB to support EL10 without unofficial repositories; strip build RPATH and ship its licence/manifest. Docker uses the distribution display.

Add continuous zoned/adaptive host PPQ, clock-aware block splitting and MIDI Clock; auxiliary sidechains shared by live/bounce/export; bounded SysEx with explicit hardware permission, MPE configuration/allocation and native libremidi UMP with lossless JSON retention and mapped high-resolution VST3 events. Add native C++/browser AudioWorklet external audio capture, bounded sequenced uploads, quota checks and durable project publication before completion. Guard recording-window closure and recover the received portion after connection errors. Scope microphone permission to the same-origin editor and include localized macOS purpose strings.

Keep the Current engine available and preserve every file from the preceding cumulative project at fixed r210. Updated IT/EN manuals are included. Test results and explicit environment limitations are recorded in the validation JSON. Physical device/driver/latency, third-party plugin, EL10/LXC/HAProxy and actual Landlock acceptance remain required. No commit, push, tag, release or production changes were performed.
