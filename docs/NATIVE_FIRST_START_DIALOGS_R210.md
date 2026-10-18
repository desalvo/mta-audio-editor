# r210 — Native startup, Windows dialogs and interface responsiveness

## Italiano

La versione rimane **0.3.0-r210**. Pacchetto cumulativo basato su
`MTA-0.3.0-r210-sample-range-profile-limits-cumulative.zip`, conservando tutti
i file precedenti, inclusi Gain mixer, lingua utente, PDF legali, quote,
editor campioni a intervallo e pannello Limiti e Quote.

### Correzioni

- Il bridge pywebview pubblica soltanto i metodi dell'API. L'introspezione
  ricorsiva non attraversa più Window, controlli WinForms/COM e stato dei
  percorsi. Il sorgente pywebview 6.2.1 conferma questa introspezione e
  l'esecuzione dei metodi Python del bridge su thread di lavoro.
- Su Windows tutti i selettori nativi di apertura/salvataggio vengono
  avviati sul thread GUI STA esistente tramite BeginInvoke. La directory
  iniziale è assoluta. Un timeout impedisce l'apertura tardiva di un dialogo
  rimasto in coda; un dialogo già visibile non scade mentre l'utente sceglie.
- Lo zoom usa un dispatch asincrono con timeout effettivo. Il primo avvio
  al 100% non accede al motore WebView e il ripristino dello zoom non blocca
  il caricamento del workspace. Le preferenze salvate rimangono disponibili.
- Crea progetto nelle app native chiede direttamente la destinazione, dopo
  la verifica delle modifiche del progetto corrente. Rimossa la riga del
  percorso con il pulsante Scegli. Annullare non crea alcun progetto; clic
  ripetuti non generano più creazioni concorrenti. Il web conserva il suo
  flusso di creazione.
- Un solo osservatore traduce l'interfaccia quando il runtime condiviso è
  presente. Cache limitata a 4096 traduzioni, azzerata al cambio lingua;
  sottostrutture inserite insieme vengono tradotte una sola volta. Nessuna
  riscrittura dell'attributo lang per ogni nodo di testo. I tooltip leggono
  textContent senza forzare il layout e aggiornano solo la sottostruttura
  inserita. Questi interventi riducono il lavoro anche aprendo About/Settings.
- Eventi di caricamento e problemi di pywebview/dialoghi confluiscono in
  `logs/native-startup.log` nella directory dati dell'utente. I percorsi
  selezionati non vengono aggiunti ai messaggi dei dialoghi.
- Cache degli asset aggiornata senza incrementare versione/revisione.

### Validazione

Test mirati: bridge con oggetti GUI che rifiutano introspezione, dispatch
Windows e timeout senza popup tardivo, annullamento, durata libera del
selettore aperto, zoom a freddo, creazione JavaScript con rientranza,
compatibilità macOS, progetti recenti, traduzioni e comportamento Settings.
Esito: **3891 passati, 5 saltati, 10 esclusi** (socket Unix dell’agente host non disponibili nell’ambiente); **69 test mirati passati**, Ruff e sintassi JavaScript superati.
Report della regressione in `validation/r210-native-first-start-*`.

**Limite:** questo ambiente non esegue WinForms/WebView2 su Windows. Le
correzioni eliminano difetti concreti verificati nel codice, ma non misurano
il tempo di risposta del computer dell'utente né certificano l'eliminazione
del blocco osservato. Sul nuovo installer controllare il primo avvio con
profilo nuovo, About, Settings, apertura/salvataggio, annullamento della
scelta percorso e un secondo avvio; poi ripetere con un progetto multitraccia
e zoom salvato diverso dal 100%. Nessun test di GPU/ROCm sul server eseguito
in questo ciclo.

## English

Version remains **0.3.0-r210**. The cumulative package retains every file in
the preceding sample-range/profile-limits package.

The native bridge exports API methods without reflecting into Window and
WinForms/COM objects. Windows file dialogs are dispatched onto the existing
STA GUI thread with a bounded start wait and no timeout for an already open
picker. Default zoom avoids touching the cold WebView; saved zoom restoration
no longer blocks workspace loading. Native Create project asks for its
save destination directly and protects against cancellation and duplicate
submissions.

Interface translation uses one shared observer, a bounded cache invalidated
on language change, and deduplicated inserted subtrees. Tooltip updates avoid
layout reads and parent-wide scans. Native startup and backend errors are
recorded in the existing rotating startup log. Asset cache keys are updated.

Results: **3891 passed, 5 skipped, 10 deselected** for host-agent Unix socket environment limitations; **69 targeted tests passed**. Ruff and JavaScript syntax checks passed.
Regression reports are included under `validation/r210-native-first-start-*`.
Tests exercise mocked Windows dispatch, actual project-creation JavaScript,
translation behavior, existing macOS/native flows and the wider application.
Real Windows cold-start and responsiveness validation is still required;
no timing improvement or server GPU certification is claimed.
