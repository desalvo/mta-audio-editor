# r210 — Collaudi sul sistema di destinazione / Target acceptance

Versione **0.3.0-r210**. Usare una copia locale del progetto e dati di collaudo separati; nessun comando seguente richiede commit, pubblicazione o modifica di server reali. Il report corrente è `R210_REAL_RUNTIME_HANDOFF_IT_EN.md`. Le sezioni cronologiche dei vecchi documenti non sostituiscono i risultati più recenti.

**Prima del collaudo:** il target dieci strumenti non è superato dal modello YourMT3 verificato. La prova inclusa è riproducibile, non una certificazione di qualità. DiffSinger richiede ancora la scelta e ammissione di una banca nativa completa. Non classificare questi due punti come semplici prove hardware.

## 1. Regressione software offline

Usare Python e dipendenze di sviluppo del progetto; CMake e compilatore C++20 nel PATH. Il flag offline riguarda i test, non modifica l'autenticazione di produzione:

```sh
MTA_TEST_OFFLINE=1 python -m pytest -q --timeout=120 --junitxml=validation/target-general.xml
```

I test opzionali non vengono trasformati in successi quando manca il loro prerequisito. Annotare separatamente gli skip, il sistema operativo, la versione Python e gli hash degli asset utilizzati.

## 2. General MIDI reale

Installare/revisionare la banca secondo la guida GM esistente. Configurare `MTA_GM_SOUNDFONT_DIR` e, se necessario, `MTA_AUDIO_CORE_PATH` per il proprio sistema; non riutilizzare i percorsi assoluti dell'ambiente di sviluppo riportati nei log.

```sh
python scripts/check_gm_soundfont.py --output validation/target-gm-programs.json
MTA_TEST_OFFLINE=1 MTA_TEST_GM_RUNTIME=1 python -m pytest -q tests/test_r210_gm_real_controllers.py tests/test_r210_gm_instrument.py tests/test_r210_gm_file_render.py
python scripts/render_gm_midi.py validation/r210-acceptance-piano.mid validation/target-piano.wav
```

Il backend portabile qui verificato non espone aftertouch. Se serve, verificare il backend FluidSynth con la libreria e le licenze corrette; l'assenza della libreria non rende il test portabile una prova di FluidSynth. Ascoltare programmi, batteria, sustain, pitch bend, program change, tempo e code; confrontare esportazione e riproduzione dal progetto. Provare finestre/riapertura progetto e routing con la propria scheda audio.

## 3. YourMT3 e benchmark

Installare il runtime con `scripts/install_studio_yourmt3.py` seguendo `YOURMT3_RUNTIME_R210.md`. Configurare le tre variabili stampate dall'installer; il runtime deve appartenere all'account MTA. Avviare dal progetto una trascrizione reale, verificare coda, cancellazione, ripresa, contabilizzazione e importazione/rilettura delle tracce MIDI. Non autorizzare automaticamente modelli o richieste di rete per far passare il test.

La prova tecnica già eseguita è disponibile come WAV/MIDI/reference/prediction/metriche `validation/r210-acceptance-*`. Per ripetere il confronto (l'uscita 2 è intenzionale se il target non è raggiunto):

```sh
python scripts/check_audio_midi_quality.py validation/r210-acceptance-ten-programs-reference.json validation/r210-acceptance-yourmt3-ten-programs.json --min-instruments 10
```

Per il collaudo musicale usare registrazioni autorizzate con partiture/etichette indipendenti revisionate. Esportare il risultato effettivo `MusicResult` e confrontarlo con `scripts/check_audio_midi_quality.py`. Non aggiungere tracce per raggiungere un numero, non usare le predizioni come ground truth e non dichiarare l'accuratezza della modalità Deep sulla base del solo modello base. Il caso incluso ha dieci programmi nella reference e cinque nella prediction: F1 0,117647 con pitch, programma, onset 50 ms e offset 100 ms. Serve ancora lavoro di modello/strategia e una verifica della modalità Deep su un insieme rappresentativo.

## 4. Vocal Studio

Per RVC/Seed usare runtime separati; `requirements-studio-conversion-runtime.txt` riporta la combinazione CPU effettivamente verificata. Installare soltanto sorgenti e componenti revisionati, con hash e licenze individuali. Il bundle operativo passa dal registro gestito e dalle policy esistenti; i log di una prova CLI non costituiscono autorizzazione commerciale.

Il runner Seed corretto è `app/seed_vc_runner.py <script-upstream> <argomenti>`; RVC usa `app/studio_offline_runner.py`. Non lanciare direttamente il CLI upstream Seed per saltare il controllo rigoroso dei pesi. Il config storico “whisper_base_f0_44k” usa realmente **Whisper small**. Non sostituire il checkpoint singing con quello speech 22,05 kHz.

Per DiffSinger installare un pacchetto OpenVPI nativo completo (non soltanto ONNX OpenUtau), config flattened, checkpoint esatto, vocoder e profilo fonetico compatibili. Configurare hash e policy secondo `STUDIO_MANAGED_ASSETS_R210_IT_EN.md` e `DIFFSINGER_DEPLOYMENT_HANDOFF_R210_IT_EN.md`, quindi:

```sh
python scripts/check_diffsinger_ready.py --json
```

Un esito ready consente un tentativo, non certifica l'audio. Eseguire canto reale IT/EN/FR, melismi, più cantanti indipendenti, curve F0/espressione, conversione, alternative per parola/sillaba/frase e riallineamento; verificare all'ascolto e nel progetto che non vengano persi dati o modificate le sorgenti in caso di errore. Provare GPU solo sul proprio hardware compatibile. RVC/Seed/Transkun/YourMT3 sono stati eseguiti qui su CPU, non CUDA/ROCm/MPS.

## 5. Browser, host e dispositivi

Su una macchina che possa installare Chromium dalla distribuzione ufficiale Playwright:

```sh
python -m playwright install chromium
python scripts/validate_midi_studio.py --help
python scripts/validate_midi_studio.py --report validation/target-midi-browser.json
```

Il comando di validazione crea un ambiente locale temporaneo autenticato; non usare un server di produzione per questa prova. Verificare tastiera, zoom, undo/redo, salvataggio/riapertura, controlli CC/bend, temi IT/EN, metronomo, mixer e stato dei job. Per i casi VST/SDK seguire i prerequisiti e le licenze dei test opzionali; non distribuire SDK o plugin con condizioni incompatibili.

Completare inoltre le prove di IPC Unix dove consentito, Windows/ASIO/macOS, driver reali, latenza, disconnessione audio e plugin/GUI nativi. Registrare dispositivo, backend, driver, buffer e risultato. Nessuno di questi controlli è sostituito dalle prove di protocollo mock o dal DOM HappyDOM.

## English acceptance boundary

The source package contains real CPU inference evidence and the general regression report. Remaining target checks cover physical audio devices, ASIO/native plugin hosts, supported GPUs, actual Chromium interaction and Unix transport where permitted. Two additional gates are **not hardware-only**: an authorized complete native DiffSinger bank is missing, and the actual ten-program YourMT3 benchmark failed. Model/strategy quality and representative recorded-music validation remain open; no ten-instrument accuracy or three-area completion is certified. Follow the steps above using isolated local test data and retain model/input/output hashes. Never turn missing assets or policy refusals into successful tests.
