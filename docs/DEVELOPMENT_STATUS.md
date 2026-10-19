# MTA Audio Editor — Development status

Versione obbligatoria: **0.3.0-r210**. Ultimo ciclo: playback, plugin opzionali e abbonamenti, 19 ottobre 2026.

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
