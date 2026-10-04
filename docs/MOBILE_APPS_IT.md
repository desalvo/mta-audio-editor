# Client Android e iOS/iPadOS

Le app mobili di MTA Audio Editor sono client nativi del backend Docker/Kubernetes. Rendering FFmpeg, Demucs, waveform e generazione MTA restano server-side.

## Connessione

Al primo avvio l'app usa automaticamente il servizio preconfigurato. **Non chiede di inserire o cambiare la URL** e **non mostra mai l'indirizzo predefinito**. Dal menu **Impostazioni server** l'utente può:

- inserire un URL personalizzato HTTPS/HTTP;
- vedere e modificare il solo URL custom che ha configurato;
- tornare al servizio predefinito senza che il relativo indirizzo venga mostrato.

Le sessioni WebView/WKWebView mantengono cookie e autenticazione del server.

## Android

- Storage Access Framework per import/export;
- `ACTION_OPEN_DOCUMENT` per upload;
- `ACTION_CREATE_DOCUMENT` per salvataggi espliciti;
- Sharesheet per condivisione;
- download autenticati con cookie WebView.

## iOS/iPadOS

- `UIDocumentPickerViewController` per import/export;
- integrazione Files/iCloud Drive;
- Share Sheet;
- cookie trasferiti da `WKHTTPCookieStore` ai download protetti.

## Job lunghi

Demucs e rendering proseguono sul server. Il client mantiene il display attivo durante i job quando possibile; se iOS/Android sospende la WebView, il job server continua e lo stato viene recuperato al ritorno.

## Build e firma

Android produce APK debug e AAB release; iOS produce `.xcarchive.zip` e, con i secret di firma, IPA/TestFlight. Le variabili di firma sono documentate nel workflow CI e non devono essere inserite nel codice sorgente.

## Modalità offline

Le app mobili non incorporano Python/PyTorch/FFmpeg completi; per separazione stems e rendering master è necessario un server raggiungibile.

### Numero di stem configurabile
La separazione strumenti supporta il parametro **Auto / 2 / 4 / 6 / 8**. Auto è il default. 2 usa il profilo voce/accompagnamento, 4 il profilo standard, 6 il profilo esteso Demucs; 8 richiede un backend con modello 8-stem configurato. Su iPhone e iPad la build corrente delega Demucs al server, quindi lo stesso parametro è disponibile su entrambi i dispositivi senza caricare PyTorch nell’app.


## On-device Demucs on iPhone/iPad (0.2.0-97)

The iOS/iPadOS client can now run stem separation locally through Core ML. The mobile workflow exposes **Auto / Local / Server** execution. Auto prefers an installed local model and falls back to server-side Demucs when the requested model is unavailable or the local device constraints are exceeded. Core ML models are provisioned as `demucs-2.mlmodel`, `demucs-4.mlmodel`, `demucs-6.mlmodel`, or `demucs-8.mlmodel` from the configured backend and are compiled/cached in the app's Application Support directory for later offline use.

The local runtime decodes the selected audio on-device, converts it to stereo 44.1 kHz Float32 PCM, processes fixed-size overlapping chunks through Core ML using all available compute units (CPU/GPU/Neural Engine where Core ML supports them), overlap-adds the results, writes WAV stems, and uploads the resulting tracks into the current project. The current local safety limit is **12 minutes per source file**; longer material falls back to the server in Auto mode. On iPhone, Auto is intentionally more conservative than on iPad because of memory/thermal constraints.

Server administrators can expose compatible Core ML Demucs models by mounting a directory and setting `MTA_DEMUCS_COREML_MODEL_DIR`. The optional `scripts/export_demucs_coreml.py` utility documents the model contract expected by the app. Model conversion is a release-engineering step and must be validated for each Demucs architecture before publishing a model.

## Aggiornamento periodico modelli Demucs
Su iPhone/iPad e Android la preferenza **Update solo con Wi-Fi** e attiva per default. Ogni 6 ore, e all avvio, il client verifica il catalogo del server e scarica solo i modelli con SHA-256 diverso. Disabilitando lo switch sono consentiti anche i download via rete cellulare. Il server Docker/Kubernetes aggiorna a sua volta il repository locale dei modelli da un manifest HTTPS configurabile.


## Separazione stem estesa model-driven

MTA Audio Editor non impone più un elenco fisso 2/4/6/8. Il server e i client mobili leggono dal catalogo/manifest le cardinalità realmente disponibili: 2, 4, 6, 8, 10, 12, 16 e anche valori superiori quando esiste un modello compatibile. Il limite tecnico di sicurezza corrente è 64 stem per singolo modello. I progetti Multitrack DAW non sono limitati dal numero di stem; i vincoli MTA8/MTA16 vengono applicati soltanto in export. I profili server aggiuntivi si configurano con `MTA_DEMUCS_MODEL_REGISTRY` o `MTA_DEMUCS_MODEL_REGISTRY_FILE`, dichiarando `model`, `stem_count`, `stem_labels` e opzionalmente `engine`/`display_name`.
