## Ciclo completato: metronomo a zone, zoom, layout personale e manuali (r210)

Baseline verificata: `0f295c2201bff0a2af5334049b91aeb1af2607b79396633bff79fcb8b9f96aa0`, 2.201 elementi, preservati nel nuovo cumulativo. Versione 0.3.0-r210 invariata.

- Primo beat a zone allineato all’inserimento; pre-roll conservato nel refresh. Il salvataggio dei marker rigenera il WAV e invalida le riproduzioni preparate. Protetti i risultati del metronomo dagli autosave accodati; rollback e pulizia temporanei in caso di errore.
- Zoom: stesso centro temporale durante preview, rilascio, pulsanti, preset e autosave, con clamp ai bordi del progetto e valori persistiti compatibili con il modello.
- Menu sempre raggiungibili, steppers compatti, barre a icone riordinabili su sei righe, monitor Job AI flottante e preferenze persistenti per utente/native. Pan sopra il valore e pulsanti FX. Gli elementi nascosti per piattaforma/permessi restano nascosti.
- Sei manuali IT/EN, online e PDF, uniformati e aggiornati; 15 schermate reali con dati sintetici, appendici condivise, tabelle e quattro grafici. PDF: utente 26+26 pagine, amministratore 15+15, VST3 8+8. Controllati copertine, font, contenuti finali, asset e limiti pagina; online fruibili anche a 390px.
- Suite estesa: **4.215 passati, 35 saltati, 10 esclusi** per test con socket agente host non disponibile; due prove C++ di latenza/stress fallite nel run concorrente, poi **entrambe passate nella verifica finale isolata**, senza allentare le soglie. Migliorato anche il feedback immediato dell’icona Pausa e il cleanup dei processi dei probe.
- **68 test mirati finali passati**, oltre agli 87 controlli dei contratti precedenti. Browser reale sui motori corrente e C++: generazione sotto autosave accodato, refresh marker durante playback, zoom ancorato, layout/monitor persistenti, menu, mobile e controlli nascosti: passati, zero errori JS.
- C++ reale: avvio 1,233s, fader 0,530s; stress rete/stalli UI: fader 0,737s, zero underrun. Misure locali, non garanzie di produzione. Compilazione C++ ABI 1, Ruff scope CI e nuovi script, Bandit alle soglie CI, sintassi JS, pip check e guardia licenze passati. Rapporti in `validation/r210-zones-layout-*`.
- Restano prove sui dispositivi fisici Windows/macOS e sul server installato/ROCm/proxy reali. Nessun commit, push, tag, release o aggiornamento di produzione eseguito.

Dettagli IT/EN: `docs/R210_ZONES_LAYOUT_MANUALS.md`.

# MTA Audio Editor — Development status

Versione obbligatoria: **0.3.0-r210**. Ultimo ciclo completato: continuità audio C++ e disinstallazione VST3, 19 ottobre 2026.

## Ciclo completato — continuità audio C++ e disinstallazione VST3 (19 ottobre 2026)

- Baseline recuperata dalla Library e verificata CRC/SHA-256: `MTA-0.3.0-r210-vst3-progress-cpp-live-controls-cumulative.zip`, `42fe3889ec2b1affce9de31e2f678716991efa451bee157112c95f9c8e4b21c6` (2.186 file).
- Utente conferma mixer, VU e avvio immediato; segnala microinterruzioni C++, Play/Pausa errato e assenza di disinstallazione VST3.
- Flusso PCM spostato in Worker/AudioWorklet con FIFO limitata, buffering adattivo e clock da campioni consumati. Handshake per reset/generazioni e gestione pausa/seek/Stop; controlli sequenza/finitezza invariati. Ricampionatore sinc/Blackman 64 tap e 1.024 fasi per frequenze diverse, bypass bit-exact alla stessa frequenza. Fallback browser precedenti mantenuto con scheduling contiguo e margine maggiore.
- Evitati seek ridondanti durante letture consecutive dei decoder. Test MP3: 2.813 seek eliminati, campioni identici; nessun vantaggio di velocità dimostrato dal microbenchmark.
- Stato Play/Pausa riallineato dopo la preparazione, icona SVG esplicita, etichette/tooltip e bridge nativi verificati.
- Disinstallazione VST3 opzionali da scheda con conferma singola, pulizia cache opzionale, avviso progetti dipendenti e dati progetto conservati. Autorizzazioni admin, ID allowlist, protezioni traversal/symlink e lock installazione/sessioni/editor; distacco atomico sullo stesso volume e namespace transitorio non eseguibile/discoverable.
- **4.187 passati, 35 saltati, 10 esclusi per socket/agente non disponibili**, zero fallimenti (circa 580s). **16 nuove regressioni finali passate**, compresi gli ultimi controlli aggiunti dopo l'avvio della suite estesa; 23 preparazione/continuità passati e 42 passati con CHOW Tape reale (uno escluso senza display). Nessun test CI disabilitato o soglia ridotta.
- Prove ASGI/Chromium/WebAudio/C++ a otto tracce: zero underrun con ritardi di rete fino a 180 ms e cinque blocchi UI da 450 ms; avvio sessione 1,239 s, risposta volume 0,538 s (0,701 s con rete rallentata). Motore corrente/editor/bozze preservati e zero errori JS. Più buffering rispetto al ciclo precedente in cambio della continuità sotto carico; nessuna garanzia di latenza universale.
- Ruff, Bandit alle soglie CI, license guard, sintassi JS, pip check passati. Tutti i 2.186 file precedenti conservati. Report in `validation/r210-continuity-*`, `r210-continuous-pcm-*`, dettagli IT/EN in `docs/CPP_CONTINUITY_VST3_UNINSTALL_R210.md`.
- Consegna: `MTA-0.3.0-r210-continuous-cpp-audio-vst3-uninstall-cumulative.zip`, intero progetto con CRC/confronto byte per byte/permessi/SHA-256 verificati durante packaging. Restano ascolto e accettazione sul server reale Rocky/HAProxy e sui dispositivi Windows/macOS.
- Versione 0.3.0-r210 invariata; nessuna modifica a produzione o azione Git.

## Ciclo completato — installazione VST3 e trasporto C++

- Baseline: `MTA-0.3.0-r210-ci-sdk-midi-progress-cumulative.zip`; tutti gli sviluppi precedenti vengono conservati.
- Richieste: barra per plugin/stato installazione; VU meter C++, controlli mixer tempestivi e pausa con Spazio.
- Cause individuate: shortcut legata ai vecchi stati; assenza di livelli nel flusso browser; coda PCM fino a oltre un secondo e salvataggio prima di ogni modifica live; pan privo di aggiornamento live.
- Implementati stato/barra per plugin con esiti persistenti; metering DSP stereo e aggiornamenti mixer live senza salvataggio; coda PCM breve e adattiva; shortcut Play/Pausa condivisa.
- Verificati 57 test mirati con CHOW Tape reale (1 escluso senza display), nove nuove regressioni e 44 regressioni legacy. Probe ASGI/Chromium/C++ a otto tracce: volume udibile dopo circa 235 ms; motore corrente e cache verificati. Regressione finale: **4,173 passati, 35 saltati, 10 esclusi per socket/agente non disponibili**, zero fallimenti (487s), con configurazione CI. Nessuna certificazione hardware o produzione implicita.

- Prima regressione locale: 12 test legacy richiedevano la variabile CI `MTA_ALLOW_INSECURE_NO_AUTH=true`; aggiornate inoltre due vecchie asserzioni che pretendevano Spazio=Stop. Tutti nuovamente passati; nessun controllo di autenticazione del prodotto rimosso. I nuovi probe server/browser usano autenticazione reale, con modalità insicura esplicitamente disabilitata.
- Ruff, Bandit alle soglie CI, license guard, pip check, sintassi JS e adapter Node passati. Report in `validation/r210-live-mixer-*`; dettagli IT/EN in `docs/VST3_PROGRESS_CPP_LIVE_CONTROLS_R210.md`.
- Consegna cumulativa `MTA-0.3.0-r210-vst3-progress-cpp-live-controls-cumulative.zip`, intero progetto; tutti i 2.173 file della baseline preservati, con verifiche CRC, byte per byte, permessi e SHA-256 durante packaging. Restano le prove sul server reale/HAProxy e sui dispositivi fisici Windows/macOS.
- Versione **0.3.0-r210** invariata. Nessun commit/push/tag/release o modifica a produzione.

## Ciclo completato — regressioni CI SDK e browser MIDI (19 ottobre 2026)

- Commit del cumulativo precedente confermato dall'utente; baseline `MTA-0.3.0-r210-playback-vst3-paypal-subscriptions-cumulative.zip`, SHA-256 `3c357e5c62eecdb04dcd32597fbda2b625ccf5d7646ae4ca11f58e3d80494bb4`. Tutti i **2.158 file conservati**, inclusi playback, plugin opzionali, abbonamenti e PayPal.
- Log ricevuti: SDK compila probe/ADelay e supera 128 blocchi, poi importa erroneamente `auth/qrcode` dal nuovo catalogo; Quality riporta 4.190 passati e un timeout su `#midiRoute`, copertura 75,43%. Bandit, audit dipendenze Python, Gitleaks e Trivy risultano passati nei log.
- Discovery VST3: percorso dei plugin opzionali spostato nel helper condiviso `runtime_paths.optional_vst3_root`, con sola libreria standard. Installer e discovery condividono il calcolo senza inizializzare autenticazione nel job SDK. Controlli percorsi/permessi e ruoli amministrativi invariati.
- Causa browser: `showMediaProgress` sostituiva il contenuto della finestra MIDI. Creato indicatore audio indipendente con proprietà per richiesta, senza sostituire/nascondere gli editor aperti. Applicato a WebAudio, nativo C++ e server C++; Stop evita riaperture dell'indicatore da risposte tardive. Cache frontend aggiornata con prefisso versione conservato.
- **Cinque nuove regressioni passate**: due processi Python `-I -S` senza site-packages e con import auth/qrcode/catalogo/FastAPI vietati; tre prove Chromium per bozze/lingue/proprietà/Stop e trasporto nativo con bridge controllato. Suite mirata: **56 mirati passati, 10 saltati**; 10 controlli finali metadati/UI passati.
- **SDK Steinberg reale compilato e sette accettazioni ADelay passate con `python -S`**: offline, chain, variable, session, stream, events, native_bridge. Commit SDK `3cdf9ca5d1f5b1b21e0a86832aa4abe55607bd96`; submodule e log nel rapporto dedicato. Nessun SDK/binario esterno aggiunto al package.
- Server HTTP locale + Chromium + WebAudio reali: otto tracce, zero rendering backend e zero errori JS; pannello effetto e valore non applicato preservati dopo playback/Stop. Ulteriore probe con finestra MIDI reale preservata. Nessun dato o pagamento di produzione usato.
- **Regressione finale: 4.164 passati, 35 saltati, 10 esclusi per socket/agente non disponibili**, nessun fallimento (455s). Il controllo del prefisso cache rilevato nel primo passaggio locale è corretto e passato nuovamente; l'ultima regressione usa la correzione. Ruff, Bandit alle soglie CI, license guard, pip check, compilazione Python e sintassi JS passati.
- Test browser live completo del runner conservato e rafforzato con assert sull'editor MIDI durante playback e dopo Stop; resta da riconfermare nella CI con host MTA compilato/plugin esterno. Nessun test CI disabilitato e nessuna soglia ridotta. Hardware Windows/macOS e server ROCm reale non certificati da queste prove.
- Dettagli: `docs/CI_SDK_MIDI_PROGRESS_R210.md`; esiti/JUnit in `validation/r210-ci-*`. Consegna `MTA-0.3.0-r210-ci-sdk-midi-progress-cumulative.zip`, intero progetto, CRC/confronto byte per byte/permessi e SHA-256 verificati nel packaging.
- Versione **0.3.0-r210** invariata. Nessun commit/push/tag/release, modifica a server reali o pagamento effettuato.


## Ciclo completato — playback, plugin opzionali e abbonamenti (19 ottobre 2026)

- Baseline: `MTA-0.3.0-r210-pages-download-cumulative.zip`, SHA-256 `86c93ca9a9989d2c9dd30c901b0b1f4a3fbd76010cdf27a7373017c2a3a8130e`. Tutti i 2.124 file conservati, incluse le precedenti correzioni CI/Pages. I permessi eseguibili POSIX della baseline vengono preservati nel cumulativo.
- Playback: eliminate conversioni integrali inutili per clip/delay; lettura diretta, cache 256 MiB e due decodifiche contemporanee in WebAudio. Anteprime float WAV riconosciute, pubblicazione atomica e cache master basata su identità sorgenti senza rileggere file interi. Rimossi i preload HTMLAudio non riutilizzati.
- C++: grafo a blocchi anche senza VST3/MIDI, sorgenti compatibili lette direttamente; conversione solo dei formati incompatibili. Confronto campione per campione con il render precedente e worker reale isolato con uscita nulla passati. Motore precedente mantenuto; fallback al mix completo solo senza runtime live.
- Preparazione: fasi distinte, nome traccia, conteggio e tempo trascorso, annullamento rispettato. Prova Chromium su otto tracce stereo di 30s: 1,653s al primo avvio, 0,227s al riavvio, zero rendering traccia/master e zero errori JS. Prova ripetibile con `scripts/validate_playback_preparation.py`.
- Catalogo opzionale MVerb, Dragonfly, CHOW Tape e Surge XT con categorie/selezione, consenso licenze, revisioni sorgenti/checksum bloccati, pubblicazione atomica e log di compilazione. Nessun binario dei plugin redistribuito nel package: build locale. Overview IT/EN e licenze incluse; verifica mensile e blocco nuove installazioni dopo 90 giorni senza revisione. Compilati e caricati realmente MVerb e i quattro Dragonfly Linux, con elaborazione stereo non silenziosa. CHOW/Surge e Windows/macOS richiedono ancora prove reali.
- Effetti interni: nome visibile **Lexicon-style reverb**, ID/preset invariati; nuovi pannelli grafici vettoriali, controlli e layout responsive. Nessun misuratore simulato.
- Contratti: modifica CPU/GPU/storage nel periodo corrente senza reset dei consumi; scelta esplicita gratuito/a pagamento. Conservati budget dei job già ammessi e storico dello storage; una modifica successiva non trasforma in pagamento le estensioni gratuite esistenti. Retry con condizioni diverse rifiutati.
- Cessazione immediata: canone proporzionale al tempo trascorso solo con servizio/billing utente abilitati; conservati accounting/extra quota. Differenze prepagate registrate come rimborsi da regolare dal gestore, senza conversione automatica in crediti.
- PayPal Sandbox/Live configurabile, Orders v2 per crediti e saldo canoni (anche dopo cessazione), segreti sigillati, verifica server di identità/importi/catture e webhook, idempotenza e storno crediti rimborsati. Pagamenti singoli: nessun addebito PayPal ricorrente automatico. Nessuna transazione reale effettuata.
- UI abbonamenti: sezioni collassabili, campi su griglia adattabile, permessi spiegati, ricerca incrementale e selezione utenti senza lista statica; eliminata l'opzione crediti disabilitata/ambigua. Asset aggiornati per invalidare le vecchie copie in cache.
- **Regressione estesa: 4.157 passati, 35 saltati, 10 esclusi per socket/agente non disponibili nell'ambiente**. Nessun fallimento. Dopo le ultime rifiniture: **40 test mirati passati**, inclusi browser desktop/mobile, PayPal, quote e playback. Ulteriori 67 passati/10 saltati per integrazione dei contratti di caricamento e script browser del server. Ruff alle stesse scope CI più nuovi helper, Bandit alle soglie CI, licenze, sintassi JS/shell e build C++ ABI 1 passati. Rapporti in `validation/r210-playback-plugins-subscriptions-*`.
- Accettazione ancora aperta: build Windows/macOS e dispositivi fisici, server reale/ROCm, plugin CHOW/Surge, PayPal Sandbox attraverso HAProxy e regolazione rimborsi monetari. Non certificato il server di produzione.
- Consegna: `MTA-0.3.0-r210-playback-vst3-paypal-subscriptions-cumulative.zip`, intero progetto. Verifiche CRC, contenuti byte per byte, file precedenti e SHA-256 eseguite durante il packaging.
- Versione **0.3.0-r210** invariata. Nessun commit/push/tag/release, pagamento o modifica ai server reali.

## Stato precedente — pubblicazione Pages (19 ottobre 2026)

- Baseline: `MTA-0.3.0-r210-docker-windows-core-build-cumulative.zip`, SHA-256 `a5983f5aeef21bc9d3d73e5bed26dc3f2d1bdd06fdfbc29566a2baed3e4e88dc`.
- Run packages `39267934184`: fermo nello step di assemblaggio, prima di configure/upload/deploy Pages.
- Run precedente `39265035765`: annullato dopo 18m50s nello stesso step; processo `gh run download` ancora attivo alla chiusura.
- Artifact sorgente `12192119228`: 5.873.100.542 byte. Il deploy scarica anche tutti gli RPM trattenuti, poi li scarta. Download privo di heartbeat e timeout; causa di rete specifica non dimostrata.
- Obiettivo: bundle Pages separato senza RPM, compatibilità manifest precedenti, avanzamento e timeout espliciti, hashing a memoria limitata. Nessuna pubblicazione remota in questo ciclo.
- Implementati bundle Pages separato e manifest con digest aggiuntivo, senza modificare quello completo per retention. Compatibilità legacy esplicita; errori sul nuovo digest/artifact non causano downgrade.
- Heartbeat ogni 30s, limite download 1.200s per canale e terminazione/attesa subprocess. Hashing incrementale; directory indipendenti per i canali. Workflow packages attivato anche per modifiche agli script, step limitato a 45m e job a 60m.
- **42 test mirati passati**, inclusi tar reale dalla shell del publisher, manifest generato dal codice effettivo del workflow, selezione nuovo/legacy, checksum errato, subprocess riuscito/fallito/bloccato e cleanup. Ruff, Bandit alle soglie CI e controllo licenze passati. L'intera suite non è stata ripetuta: nessuna modifica runtime/audio.
- Consegna: `MTA-0.3.0-r210-pages-download-cumulative.zip`; report in `validation/r210-pages-download-result.json` e JUnit adiacente. Tutti i 2.121 file della baseline conservati; CRC, confronto byte per byte e SHA-256 verificati durante packaging.
- **Accettazione remota ancora aperta**: integrare anche workflow e assembler nel repository packages, poi ripubblicare dal nuovo commit verificato dalla matrice. Non basta rilanciare il vecchio manifest: contiene ancora il bundle da 5,9 GB. Istruzioni in `docs/NATIVE_SERVER_PAGES_ARTIFACT_DEPLOY_IT.md`.
- Versione 0.3.0-r210 invariata; nessun commit/push/tag/release, annullamento job o deploy remoto effettuato.

## Stato corrente — build Docker e Windows

- Baseline: `MTA-0.3.0-r210-ci-license-signed-rpm-cumulative.zip`, SHA-256 `6f1ad7b58a8fb67f898090e76c67a8adf86f900837eab48c5744036678d63930`. Tutti i suoi 2.112 file conservati.
- Docker: il primo stage copia anche `native/third_party/miniaudio` nella directory sorella del core.
- Windows: `NOMINMAX` sul target CMake e chiamate `std::max` resistenti alle macro nel callback audio; nessun warning soppresso.
- **60 test mirati passati**: 39 build/DSP/server più 21 trasporto/cattura/gate CI. Compilazioni isolate con i soli COPY Docker, sia normale sia con macro Win32 iniettate, riuscite; ABI core/trasporto e simboli cattura verificati.
- Ruff, Bandit alle soglie CI e controllo licenze: passati. Aggiornate le note miniaudio.
- L’immagine Docker completa e MSVC reale non sono eseguibili in questo ambiente: conferma richiesta ai runner CI. Non è stata ripetuta l’intera suite in questo ciclo.
- Consegna: `MTA-0.3.0-r210-docker-windows-core-build-cumulative.zip`; rapporti in `validation/r210-container-windows-result.json` e JUnit/log adiacenti. CRC, confronto byte per byte e SHA-256 fanno parte della creazione del cumulativo.
- Versione 0.3.0-r210 invariata; nessun commit/push/tag/release o intervento sui server reali.

## Checkpoint CI precedente (15:16)

- Corrette la collocazione del plugin di prova Quality e la rimozione automatica delle dipendenze nel test RPM firmato. Nessuna modifica al runtime applicativo o ai requisiti RPM.
- **35 test mirati passati**, incluso il license guard che falliva nella CI; Ruff, Bandit e sintassi shell passati. Download reale del plugin bloccato a checksum, elaborazione audio e audit sorgenti passati con fixture esterno. Guard del test distruttivo eseguito e rifiutato correttamente fuori da CI.
- I log allegati confermano per Rocky9, Rocky10 e Alma10: compilazione/payload offline, installazione/reinstallazione e ciclo DNF riusciti. Nuova conferma del test firmato ancora richiesta sulla CI reale.
- Non è stata ripetuta l’intera suite audio in questo ciclo: nessun codice runtime è cambiato; i log Quality ricevuti riportano 4.137 passati e un solo fallimento, quello corretto. Le 4.135 prove locali del ciclo precedente restano una verifica storica, non un nuovo esito di questo ciclo.
- Baseline corrente: `MTA-0.3.0-r210-ci-quality-sast-rpm-fixes-cumulative.zip`, SHA-256 `277524484124d8c473217cb19372c813dcc8473c34a65a6866ad05e695b3566c`; tutti i suoi 2.104 file conservati.
- Consegna: `MTA-0.3.0-r210-ci-license-signed-rpm-cumulative.zip`, verifica CRC e byte per byte e SHA-256. Risultati: `validation/r210-ci-gates-result.json`.

## Checkpoint precedente

- Baseline: MTA-0.3.0-r210-vst3-server-editor-cumulative.zip, SHA-256 a40f80f9ee7e4a94975407ed20d2b31e2192b1139fc602dc5cfedf7f2727e96a.
- Ciclo precedente: 4.128 test passati, 6 saltati, 10 esclusi per l’ambiente. GUI originale VST3, mappe tempo, sidechain, MIDI e acquisizione integrati.
- Segnalazioni CI attuali: Quality non importa numpy prima del controllo ABI; dependency audit non risolve python-rtmidi senza header ALSA; EL10 non risolve il download X.Org; log Rocky9 da analizzare per errore linker.

## Macroaree

| Area | Stato | Evidenza / limite |
|---|---|---|
| Editor, progetti, mixer, motori AI, coda e accounting | Conservati dalla baseline | Nessuna modifica funzionale in questo ciclo; coperti dalla regressione automatica, accettazione reale distinta |
| Motore C++ e hosting VST3/VSTi server/nativo, MIDI e acquisizione | Integrati nel cumulativo precedente | GUI reale, sidechain e MIDI provati localmente; kernel/container e dispositivi fisici restano da validare |
| Quality e audit nativo | Correzioni implementate e prove locali passate | Ambiente pulito/ABI, Ruff, Bandit e audit strict; Python 3.14 GitHub da riconfermare |
| Packaging server RPM/DEB | Correzioni implementate | Display sorgente locale e DEB offline passati; RPM EL9/EL10 da riconfermare in CI |
| Build e installazione native multipiattaforma | Pipeline conservata | Build Windows/macOS/Linux effettive da confermare dopo lo sblocco dei gate |
| ASIO dedicato e SMF2/SMPTE | Non implementati nel ciclo precedente | Lavoro futuro distinto dal ripristino CI corrente |
| Plugin open-source opzionali | Catalogo e installazione sorgente implementati in questo ciclo | MVerb/Dragonfly Linux provati; CHOW/Surge e native da validare |
| AI Vocal Studio, AI Multi-Track Audio-to-MIDI | Backlog futuro, non avviato | Avvio solo su richiesta futura |

## Correzioni implementate

- Quality: installazione di NumPy prima dell’import/controllo ABI Pedalboard, senza upgrade delle versioni NumPy già presenti (compatibilità Intel macOS).
- SAST/audit: header ALSA/JACK provisionati nel job; audit nativo completo e strict mantenuto.
- Display RPM/DEB: tarball sorgente X.Org 21.1.24 originale incluso con licenze e checksum bloccato; nessun download durante la compilazione. Override solo da file locale e con identica verifica digest.
- Rocky9/EL10: libatomic esplicita nei prerequisiti di build e nelle dipendenze RPM; libatomic1 anche nelle dipendenze DEB.

## Verifiche concluse

- 18 test mirati passati (nuove regressioni più packaging).
- Ruff allo scope CI e sui build script modificati: passato. Bandit alle soglie CI e controllo licenze: passati.
- Ambiente Python vuoto: installazione runtime VST3 con NumPy e controllo ABI passati.
- Audit strict dei 12 pacchetti nativi risolti: nessuna vulnerabilità nota. Python 3.12 locale; job Python 3.14 da confermare su GitHub.
- python-rtmidi 1.5.8 compilato da sdist con header ALSA.
- Display ricompilato dal tarball locale: binario identico al precedente, nessun RPATH di build, avvio e frame JPEG passati in modalità test TCP autenticata.
- Nuovo DEB estratto: 293 file applicativi confrontati byte per byte; installazione pip offline, pip check e smoke ABI C++/VST3 passati.

## Esito finale del ciclo

- Regressione finale: **4.135 test passati, 6 saltati e 10 esclusi** per i limiti dell’ambiente (socket agente AF_UNIX). Nessun errore o fallimento nel JUnit; copertura complessiva 76.14%.
- I sei skip riguardano quattro prove opzionali Steinberg SDK, una GUI desktop nativa senza DISPLAY e le API Win32. I test della GUI originale server e browser sono stati eseguiti con plugin reali e display TCP autenticato di test.
- Archivio cumulativo: `MTA-0.3.0-r210-ci-quality-sast-rpm-fixes-cumulative.zip`; conservati tutti i 2.084 file della baseline, con nuovi test, sorgente X.Org e rapporti di validazione. Il processo di consegna verifica CRC, tutti i contenuti byte per byte e SHA-256.
- Risultati del ciclo: `validation/r210-ci-repair-result.json`, JUnit e report audit nello stesso percorso.
- Revisione invariata; nessun commit/push/tag/release o accesso al server di produzione.

## Pendenti / limiti

- Verifica CI GitHub su Rocky9/10 dopo il commit dell’utente.
- Accettazione sul server EL10/LXC: Landlock e plugin Linux effettivi.
- Prove con hardware audio/MIDI, driver UMP e latenza fisica.
- Selettore ASIO dedicato e SMF2/SMPTE fuori dal ciclo precedente.
- Raccolta plugin open-source, AI Vocal Studio e AI Multi-Track Audio-to-MIDI: backlog futuro, non avviato.

## Prossimi passi

L’utente applica il cumulativo e rilancia CI e packaging. Confermare prima Quality/SAST su Python 3.14 e i tre target RPM Rocky9/Rocky10/Alma10; poi build native. Dopo CI verde procedere all’accettazione EL10/LXC e dispositivi fisici. Nessuna certificazione del server è dedotta dalla sola regressione locale.


## Ciclo successivo — CI del 19 ottobre, ore 15:16 Europe/Rome

Nuovi log ricevuti: Quality fallisce solo nel license guard perché il plugin di test CHOW è scaricato nel checkout; le tre build RPM ora compilano, installano e aggiornano, ma il test del repository firmato non risolve alcune dipendenze X11 dopo la rimozione dell’applicazione. Cause confermate nei log:

- Quality: 4.137 passati, 13 saltati, un solo fallimento, `test_source_license_gate`, dovuto al plugin di prova dentro `.external` del checkout. SAST non riporta nuovi errori.
- Tutti e tre gli RPM: compilazione, installazione/reinstallazione e version cycle superati; il test firmato rimuove `xkbcomp` (anche `libXtst`/`xkeyboard-config` su EL9) tramite l’autoremove implicito, poi disabilita i repository che potrebbero reinstallarli.

Correzioni implementate: fixture Quality spostato sotto `RUNNER_TEMP`, con percorso di test corrispondente; disattivazione del solo cleanup automatico nella rimozione preparatoria del test firmato. Controllo licenze, dipendenze RPM, firme e isolamento del repository rimangono attivi. Verifiche mirate concluse: 35 passati; r210 invariata. Nessun commit/push/tag/release o intervento sui server reali. Baseline: MTA-0.3.0-r210-ci-quality-sast-rpm-fixes-cumulative.zip (SHA-256 277524484124d8c473217cb19372c813dcc8473c34a65a6866ad05e695b3566c).


## Prossima verifica richiesta

Dopo l’applicazione e il commit dell’utente: rilanciare Quality e i tre job RPM. Verificare la conclusione del test repository firmato mantenendo attivi `gpgcheck=1`, `repo_gpgcheck=1` e il test dei metadata alterati. Il controllo licenze deve continuare a rifiutare plugin nel checkout, anche sotto `.external`.


## Ciclo Docker — 19 ottobre 2026 ore 15:55 Europe/Rome

Baseline: `MTA-0.3.0-r210-ci-license-signed-rpm-cumulative.zip`, SHA-256 `6f1ad7b58a8fb67f898090e76c67a8adf86f900837eab48c5744036678d63930`. Log allegato: fallisce lo stage `audio-core-build`, `device_transport.cpp` non trova `../third_party/miniaudio/miniaudio.h`. Il Dockerfile copia solo `native/audio_core` e omette il fratello `native/third_party/miniaudio`. Corretto il COPY Docker; entrambe le compilazioni su contesto isolato, normale e con macro Win32 iniettate, sono passate. Revisione invariata.


Aggiornamento nello stesso ciclo: ricevuto anche il fallimento MSVC C2589 sulle chiamate `std::max` del callback. Causa: macro Win32 `max` introdotta attraverso miniaudio. Applicati `NOMINMAX` al target Windows e chiamate resistenti alle macro. 60 test passati (39 build/DSP/server, 21 trasporto/cattura/gate CI). MSVC reale non disponibile localmente. I warning C4324/C4244/C4456/C4245 e la nota `CMAKE_BUILD_TYPE` non sono l’errore fatale segnalato e non vengono soppressi.
