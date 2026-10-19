# MTA Audio Editor — Development status

Versione obbligatoria: **0.3.0-r210**. Ciclo iniziato il 19 ottobre 2026 dopo il commit del cumulativo VST3 server editor.

## Stato iniziale verificato

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
| Plugin open-source opzionali, AI Vocal Studio, AI Multi-Track Audio-to-MIDI | Backlog futuro, non avviato | Avvio solo su richiesta futura |

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
