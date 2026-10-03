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
