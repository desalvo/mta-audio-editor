# r210 — Installazione e collaudi DiffSinger ONNX / Deep

Versione 0.3.0-r210 invariata. Questi passi riguardano una copia locale o un ambiente di collaudo, non un server reale da modificare automaticamente. Report: `R210_DIFFSINGER_DEEP_CLOSURE_IT_EN.md`. Il target qualitativo dieci–sedici strumenti rimane non superato sullo stress test incluso: non confonderlo con il completamento tecnico delle pipeline.

## Qixuan: banca completa pronta

È fornito separatamente `MTA-Qixuan-2.7.0-onnx-release-bundle.zip`: comprende integralmente Qixuan 2.7.0 e il vocoder PC-NSF-HiFiGAN 2025.02, con immagini, condizioni e avvisi originali. Leggere i documenti inclusi prima dell'uso. La banca non viene venduta e il builder/installatore non conferisce diritti. Il vocoder è NC; Qixuan proibisce il servizio di sintesi a pagamento. Le policy MTA richiedono la revisione individuale di cantante, vocoder e componenti. La conferma dell'operatore nelle impostazioni è una scelta di distribuzione/servizio, non un test da aggirare.

Per ricreare il bundle dai due download originali, senza rete nel builder:

```sh
python scripts/build_qixuan_onnx_bundle.py \
  --bank /percorso/Qixuan_v2.7.0_DiffSinger_OpenUtau.zip \
  --vocoder /percorso/pc_nsf_hifigan_44.1k_hop512_128bin_2025.02.oudep \
  --output /percorso/MTA-Qixuan-2.7.0-onnx-bundle.zip
```

Provenienza e SHA obbligatori sono nel report e nel builder. Ogni file originale è conservato byte per byte. La copia del codice MTA nel bundle è evidenza di provenienza; l'esecuzione usa il runner fisso dell'applicazione, non script scelti dal client.

Creare un runtime CPU isolato Python 3.12 con un interprete regolare (il controllo SHA dell'interprete non accetta symlink):

```sh
python3.12 -m venv --copies /opt/mta/diffsinger-onnx
/opt/mta/diffsinger-onnx/bin/python -m pip install -r requirements-studio-diffsinger-onnx.txt
```

Su Windows adattare i percorsi all'interprete `Scripts/python.exe`, senza scegliere l'eseguibile della GUI come Python. Eseguire con l'account MTA in una directory leggibile da tale account. La prova effettuata qui è Linux CPU; gli altri sistemi sono collaudi di destinazione.

Impostare `MTA_DIFFSINGER_PYTHON` al percorso assoluto dell'interprete e `MTA_DIFFSINGER_PYTHON_SHA256` al suo SHA-256. Il resto dell'ambiente è prodotto dal registro per la banca selezionata. Importare il bundle dal gestore asset: il caricamento verifica tutti i byte e lo installa **disabilitato**. Dopo la revisione delle condizioni e delle policy nell'ambiente appropriato, abilitarlo come previsto dall'interfaccia; non fabbricare autorizzazioni scrivendo nei JSON interni. Le conferme richieste in `app/model_license_policy.py` rimangono obbligatorie.

In Vocal Studio scegliere DiffSinger e la banca Qixuan 2.7.0 per il singolo cantante. Il profilo fornito dichiara **inglese e vocalizzi**; non espone IT/FR come lingue certificate di questa banca. Provare prima una frase breve, poi testo, note ripetute/melismi, curve F0/vibrato, dinamica, più cantanti e salvataggio/riapertura. Le curve predefinite breathiness -48 dB e voicing -12 dB sono controlli dichiarati, modificabili tramite espressione; non sono predizioni di varianza.

Non eseguire direttamente un modello non revisionato né sostituire il vocoder con uno che abbia parametri mel diversi. Il percorso nativo OpenVPI `.ckpt` resta disponibile: continuare a usare i suoi requisiti specifici, non rinominare ONNX in `.ckpt`. `scripts/check_diffsinger_ready.py --json` distingue i formati e non certifica la qualità dell'audio.

## YourMT3 PS accanto al modello noPS

Installare prima il runtime noPS già documentato in `YOURMT3_RUNTIME_R210.md`. Per aggiungere PS senza alterare i file noPS:

```sh
python scripts/install_studio_yourmt3_ps.py \
  --runtime /opt/mta/studio-yourmt3 \
  --test-audio /percorso/campione-musicale-autorizzato.wav \
  --accept-apache-2-license
```

`--checkpoint-local` consente un checkpoint originale già scaricato; dimensione e SHA restano obbligatori. L'installer crea la nuova directory PS e un receipt separato, converte soltanto il checkpoint fissato con il loader sicuro ed esegue un'inferenza reale prima di dichiararlo testato. Per selezionarlo:

```text
MTA_STUDIO_TRANSCRIBER=yourmt3
MTA_STUDIO_YOURMT3_RUNTIME=/opt/mta/studio-yourmt3
MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON=/opt/mta/studio-yourmt3/bin/python
MTA_STUDIO_YOURMT3_VARIANT=ps
```

Fermare i job prima di cambiare la configurazione e riavviare l'istanza di collaudo. Rimuovere l'ultima variabile o usare `nops` per tornare al default; nessun file noPS viene sovrascritto. PS significa addestramento con pitch shifting, non alterazione automatica dell'intonazione in ingresso. Non è dimostrato superiore sullo stress test qui eseguito.

Le classi di canto sono mantenute come voce/coro. I programmi GM 53/52 sono proxy di riproduzione dichiarati; velocity 96 è generata. Non sono rilevati automaticamente CC, bend o dinamica calibrata. I programmi strumentali sono rappresentativi delle classi del modello e possono richiedere correzione del timbro nel MIDI editor.

## Deep reale e ripresa

Installare Basic Pitch ONNX dal gestore esistente e configurare Demucs 4.1.0 in un runtime separato, con modelli autorizzati già disponibili. In questo ambiente è stato usato il modello ufficiale HTDemucs safetensors indicato nel report, non download durante l'inferenza. Configurare, secondo i propri percorsi:

```text
MTA_DEMUCS_PYTHON=/opt/mta/stems/bin/python
MTA_DEMUCS_DEVICE=cpu
```

La scelta GPU può essere eseguita successivamente sul proprio hardware supportato. La cache Hugging Face e il suo snapshot attivo devono appartenere all'account MTA. Per verifiche offline impostare `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` e disabilitare la manutenzione modelli automatica come descritto nella guida offline.

Nell'app scegliere Audio-to-MIDI, modalità Maximum/Deep, una regione autorizzata breve e i modelli installati. Verificare che le parti derivino dagli eventi effettivamente inferiti, che Basic Pitch non trascriva la batteria e che un'assegnazione strumentale ignota rimanga tale. Provare poi cancellazione, ripresa dello stesso job, salvataggio, riapertura e uso CPU/GPU sul proprio sistema. Una ripresa valida non deve ripetere/addebbitare gli stadi già conservati; dopo modifiche di modello/runtime/policy deve invece invalidarli.

Il test tecnico salvato comprende otto inferenze reali e replay senza nuove esecuzioni. Non confondere il replay con una nuova inferenza. Usare registrazioni e MIDI di riferimento revisionati per valutare l'accuratezza musicale; i risultati sul mix sintetico difficile sono esplicitamente negativi anche dopo PS/Deep.

## Regressione e risorse temporanee

Per sistemi con disco temporaneo limitato:

```sh
MTA_TEST_OFFLINE=1 python -m pytest -q --timeout=180 \
  -o tmp_path_retention_policy=failed -o tmp_path_retention_count=1 \
  --junitxml=validation/target-general.xml
```

Questa opzione elimina i temporanei dei test superati; non salta test né nasconde errori. Per i test GM, browser, VST e dispositivi seguire i prerequisiti già documentati. Chromium, host/driver fisici, ASIO, IPC locale e GPU non sono simulati da fixture. Basic Pitch upstream dichiara TensorFlow nei metadati: il backend ONNX qui eseguito non lo utilizza; il relativo avviso `pip check` è conservato, senza installare TensorFlow inutilmente o falsificare i metadati.

## English

Use the complete separately supplied managed Qixuan/vocoder bundle and an isolated regular Python interpreter pinned by SHA-256. Import installs it disabled; review the actual singer/vocoder/component terms and existing operator confirmations before enabling. No commercial entitlement is granted. English/vocalise profiles, score F0, explicit variance controls and real CPU words/melismas were tested; other languages, banks, devices and GPUs need their own acceptance.

Add the PS checkpoint only to a verified noPS runtime with the new installer, then explicitly select `MTA_STUDIO_YOURMT3_VARIANT=ps`. The original noPS runtime remains unchanged. Deep genuinely executed separation/transcription/reconciliation and eight-stage replay. Actual ten-program stress-test accuracy still failed; extra parts, unassigned instruments and model-class proxies do not satisfy ten correct instruments. Follow the commands above in an isolated local/staging copy, retain hashes and record musical/browser/hardware acceptance separately.
