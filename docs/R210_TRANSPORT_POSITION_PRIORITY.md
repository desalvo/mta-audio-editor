# r210 — Posizionamento del transport e griglia metronomo / Transport positioning and metronome grid

## Italiano

Il Play usa l’ultima posizione impostata esplicitamente tramite click sul righello o sulla timeline, click semplice su un segmento con Select, frecce, slider, ritorno all’inizio o campo numerico. Il click semplice su un segmento continua a selezionarlo; trascinamento, selezione multipla, snap e storico restano operazioni di editing. Il posizionamento durante la riproduzione esegue un seek mantenendo lo stato richiesto di Play/Pausa.

I click precedentemente aggiornavano soltanto il cursore visivo. La ripresa poteva quindi riutilizzare il clock precedente. Le risposte asincrone del bridge nativo potevano inoltre riportare indietro il cursore. Ora i comandi nativi sono ordinati, gli aggiornamenti obsoleti vengono ignorati e la preparazione usa l’ultima posizione richiesta. La preparazione nativa avviene inizialmente in pausa: il dispositivo parte soltanto dopo il posizionamento. Il server mantiene l’intento Play/Pausa anche durante più seek ravvicinati e controlla la generazione dopo lo sblocco asincrono dell’audio.

Nella finestra della griglia metronomo di zona, «Applica e rigenera zona» e «Riporta in Auto» usano gli stili delle azioni delle finestre: sfondo, colore del testo e disposizione sono coordinati e leggibili anche su larghezze ridotte.

Il log CI allegato è la precedente esecuzione sul commit `11e7d366`: il confronto testuale sullo zoom era già corretto nel cumulativo di partenza. Il relativo test è passato nuovamente. Il nuovo cumulativo conserva anche le correzioni allo zoom decimale e alla presentazione dei consumi contabilizzati CPU/GPU.

Validazione: 232 test distinti mirati passati; 17 scenari di concorrenza Node; Chromium reale con server HTTP autenticato e motori corrente/C++ AudioWorklet, 6 scenari per motore senza errori JavaScript; pulsanti verificati IT/EN con preferenza OS chiara/scura e contrasto almeno 4,5:1. Build C++ ABI 1, Ruff, Bandit alle soglie CI, sintassi JavaScript, pip check e guardia licenze passati. Non è stata rieseguita l’intera suite in questo ciclo. Il dispositivo nativo è stato provato con backend null esplicito e bridge simulato, senza dichiarare prove su hardware fisico.

Dopo l’installazione, verificare sul dispositivo reale: riprodurre, mettere in pausa, scegliere un altro punto con click, premere Play; ripetere con frecce e input numerico, poi dopo Stop. Ripetere con entrambi i motori. L’audio deve partire dal punto scelto e il Play/Pausa deve rimanere coerente. Controllare i due pulsanti della griglia metronomo di zona. Resta da eseguire la CI remota dopo il commit gestito dall’utente.

## English

Play uses the latest explicit position requested through the ruler or timeline, a simple Select click on a clip, arrows, seek slider, return to start, or numeric transport input. A simple clip click still selects the clip; dragging, multiple selection, snap and history retain their editing behavior. Positioning during playback seeks while preserving the requested Play/Pause state.

Some clicks previously changed only the visible cursor, allowing playback to reuse its old clock anchor. Delayed native bridge responses could also overwrite a newer position. Native controls are now ordered and stale replies ignored; asynchronous preparation honors the latest requested position. Native preparation starts paused, and device playback begins only after positioning. Server playback preserves Play/Pause intent across repeated seeks and checks the session generation again after asynchronous audio unlocking.

The zone metronome grid's “Apply and regenerate zone” and “Return to Auto” buttons use the dialog action styles with coordinated backgrounds, text colors and responsive layout.

The attached CI log is the older run at commit `11e7d366`: its stale zoom source assertion was already corrected in the starting cumulative package, and its regression passed again. This package also preserves decimal zoom persistence and the accounted CPU/GPU usage presentation from that baseline.

Validation: 232 distinct targeted tests passed; 17 deterministic Node race scenarios; real Chromium with authenticated HTTP and Current/C++ server AudioWorklet playback, six scenarios per engine and no JavaScript errors; IT/EN zone buttons checked under light/dark OS preferences with at least 4.5:1 contrast. C++ ABI 1 build, Ruff, Bandit at CI thresholds, JavaScript syntax, pip check and license guard passed. The entire suite was not rerun in this cycle. Native device checks used the explicit null backend and simulated bridge, without claiming physical hardware validation.

After installation, test physical devices: play, pause, click a different timeline position and Play; repeat using arrows and numeric input, then after Stop, with both engines. Audio must start from the chosen position and Play/Pause must remain consistent. Check the two zone grid buttons. Remote CI remains pending the user's commit. Version 0.3.0-r210 is unchanged; no commits, pushes, tags, releases or production changes were made.
