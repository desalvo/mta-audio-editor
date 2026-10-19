# CI SDK VST3 e conservazione degli editor — 0.3.0-r210

## Diagnosi dai log ricevuti

Il job SDK compila correttamente il probe e ADelay, ed esegue 128 blocchi offline.
La catena successiva fallisce invece durante gli import Python:
`vst3_host → optional_plugins → auth → qrcode`. La ricerca dei percorsi dei plugin
non deve inizializzare autenticazione o installer.

Quality riporta un solo fallimento dopo 4.190 test passati: manca `#midiRoute`
dopo la riproduzione MIDI hardware. La nuova preparazione audio utilizzava
`showMediaProgress`, che sostituiva il contenuto della finestra comune. Quindi
la finestra MIDI perdeva i suoi controlli e le bozze prima dello Stop.
La copertura del run ricevuto è 75,43%, sopra il limite del 70%.
Bandit, audit dipendenze Python, Gitleaks e Trivy risultano già passati nei log;
Trivy riporta zero vulnerabilità per `requirements.txt`.

## Correzione

- `runtime_paths.optional_vst3_root` calcola il percorso gestito utilizzando
  esclusivamente la libreria standard. Il discovery SDK utilizza questa funzione;
  il catalogo la condivide conservando il proprio contesto dati. Nessun nuovo
  pacchetto Python è necessario nel job SDK.
- Conservati i controlli sui percorsi VST3 del server: esclusione dei progetti,
  risoluzione dei link, directory non scrivibili da gruppo/altri e autorizzazioni
  amministrative del catalogo. Nessuna riduzione dei controlli di sicurezza.
- La preparazione ha una superficie indipendente, `#audioPreparation`, con fase,
  dettaglio, avanzamento e Stop. WebAudio, trasporto nativo C++ e trasporto C++ del
  server non sostituiscono né nascondono la finestra MIDI/plugin/campioni aperta.
- Ogni preparazione possiede il proprio indicatore: un completamento tardivo non
  chiude quello di una richiesta successiva. Stop impedisce la ricomparsa
  dell'indicatore durante la decodifica residua.
- Aggiornate le chiavi cache frontend, mantenendo il prefisso `0.3.0-r210`.
  Versione e revisione del prodotto non cambiano.
- Il test CI browser live verifica esplicitamente che l'editor MIDI sia ancora
  visibile durante la riproduzione hardware e dopo Stop. Nessun test viene
  disabilitato e nessun requisito di copertura o audit viene abbassato.

## Verifiche ripetibili

`python -m pytest -q tests/test_r210_ci_playback_isolation.py`

Due casi eseguono discovery e import della catena in un processo `-I -S`, senza
site-packages, vietando esplicitamente l'import di `auth`, catalogo, FastAPI e
qrcode. Tre casi Chromium verificano conservazione bozze, proprietà dell'indicatore,
Stop, lingue IT/EN e trasporto nativo. Nel caso nativo il bridge del dispositivo è
controllato dal test: non è una prova su dispositivo fisico.

`python scripts/validate_playback_preparation.py --report validation/playback-local.json`

Questo probe usa un server HTTP locale temporaneo, Chromium, otto tracce stereo e
WebAudio reali. Verifica cache, assenza di rendering backend superfluo, assenza di
errori JS e conservazione di un valore non applicato nel pannello riverbero durante
playback e Stop. Non usa dati di produzione.

Compilati inoltre il probe con SDK Steinberg reale e il plugin ADelay. Tutti i
sette script `scripts/test_vst3_adelay_*.py` sono stati eseguiti con `python -S`:
offline, chain, variable, session, stream, events e native_bridge. Commit e
submodule effettivamente usati sono registrati in
`validation/r210-ci-real-sdk-acceptance.json`. Sorgenti e binari SDK esterni non
sono inclusi nel cumulativo.

I risultati della regressione estesa sono nel rapporto JSON e nei JUnit di questo
ciclo. Il test completo Chromium + worker server + plugin esterno richiede il
runtime MTA compilato, il plugin di prova e l'ambiente di confinamento del runner;
resta attivo nella CI. Le prove locali descritte non certificano hardware audio,
Windows/macOS o il server ROCm reale.

## English

The SDK job failed because path discovery imported the optional installer and
then authentication/qrcode. Managed plugin paths now live in a shared stdlib-only
helper. Server path checks and catalog administrator permissions remain intact.

The MIDI browser timeout was caused by the shared media-progress dialog replacing
the editor DOM. Audio preparation now owns a separate progress surface in all
three transports, preserving controls and unsaved edits. Ownership prevents stale
cleanup from hiding a newer request; Stop prevents progress from reopening.
Frontend cache keys retain the fixed product revision.

The five new regressions cover dependency-free SDK imports and real Chromium
editor retention, including a controlled native bridge. A separate disposable
HTTP/WebAudio probe verifies eight-track playback and plugin draft retention.
The real Steinberg SDK/ADelay build and all seven acceptance scripts pass with
site-packages disabled. The full server live browser test remains enabled in CI;
its specialized runtime/device environment is distinct from the local checks.
Security checks and coverage thresholds are unchanged. No commit, push, release,
payment or production-server action is performed by this package.
