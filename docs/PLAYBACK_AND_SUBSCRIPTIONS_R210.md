# Playback, contratti correnti e PayPal — 0.3.0-r210

## Preparazione audio / Audio preparation

### IT

Il player WebAudio legge direttamente la sorgente quando non occorrono insert
renderizzati o trasformazioni di tempo/pitch: posizioni dei segmenti e delay,
anche negativi, sono programmati sul clock audio condiviso. Non si genera un WAV
completo per il solo spostamento di un segmento. La decodifica è limitata a due
tracce simultanee e non duplica il buffer del file in memoria. La cache mantiene
al massimo 256 MiB di audio, deduplica richieste simultanee ed elimina le voci meno
recenti; i buffer già in riproduzione rimangono validi. Progetti molto lunghi
possono comunque richiedere memoria per i buffer attivamente riprodotti.

Il pre-caricamento HTMLAudio precedente non viene avviato dal player WebAudio:
evitati download o rendering anticipati che non venivano poi riutilizzati.
Le anteprime renderizzate sono pubblicate atomicamente; le anteprime master WAV
sono riutilizzate in base a progetto, identità sorgenti e motore, con due mix
recenti per progetto. La verifica non legge/hash-a ogni volta i file audio interi.
Restano fuori dalle cartelle progetto e dagli export portabili.

Il trasporto C++ usa il grafo live anche senza plugin esterni, se il runtime live
è disponibile. Le sorgenti WAV/FLAC e altri formati seekable compatibili con
sample rate/canali vengono lette a blocchi; conversione integrale solo per formati
incompatibili. Clip, delay e input gain sono applicati nel grafo prima degli insert.
Anche il server C++ usa il percorso live senza richiedere la presenza di un VST3.
Il motore originario rimane selezionabile; la mancanza del runtime live nativo
mantiene il percorso di compatibilità con rendering del mix.

La preparazione distingue salvataggio, caricamento sorgente, rendering backend,
decodifica, verifica/conversione, inizializzazione DSP/insert e dispositivo.
Mostra nome traccia, conteggio tracce e tempo; le fasi di durata sconosciuta usano
un indicatore indeterminato, senza fingere un avanzamento misurato nei plugin.

Prova Chromium locale: 8 tracce stereo da 30s, segmenti spostati e delay, apertura
e playback reali via ASGI. Circa **1,7s** al primo avvio e **0,2s** al riavvio con
cache, zero richieste di rendering traccia/master e zero errori JS. Sono tempi
dell'ambiente di test, non una garanzia sui dispositivi dell'utente. Confronto
campione per campione tra blocchi raw C++ e render precedente: passato (delay
negativo, selezione sorgenti, silenzi, gain). Dispositivi Windows/macOS e il server
ROCm reale restano da verificare dopo la build.

### EN

Dry WebAudio playback schedules source clips/delays directly on the shared clock,
without whole-track backend rendering. At most two tracks decode concurrently;
there is no extra encoded-buffer copy. A 256 MiB LRU cache deduplicates concurrent
requests while active playback buffers remain alive. Obsolete HTMLAudio preloads
are suppressed. Rendered track previews are atomic; deterministic master-WAV
previews are reused and retain two recent mixes per project, outside exports.

C++ now streams ordinary projects through its block graph as well as VST3/MIDI
projects. Compatible seekable sources bypass full preparation renders, and only
incompatible formats require conversion. Clip placement, negative delay and input
gain are applied before inserts. The selected server C++ engine follows the same
live route. Native installations without a live runtime retain the compatibility
mix-render path. Preparation identifies stage, track, track count and elapsed time.

The local eight-track Chromium exercise measured approximately 1.7s initial start
and 0.2s cached restart with no backend track/master render requests or JS errors.
Raw C++ samples match the earlier rendered timeline within the test tolerance.
These figures describe the test host, not production/hardware certification.

## Quote del contratto corrente / Current contract allowances

Gli admin selezionano l'utente dai risultati incrementali per nome, username o
email. Non c'è più una lista statica separata. Le impostazioni generali, pagamenti,
quote correnti e cessazione sono organizzati in sezioni collassabili.

La modifica CPU/GPU/storage non cambia inizio/fine del periodo né i consumi già
registrati. Ogni aumento richiede scelta esplicita gratuito/a pagamento. Gli
aumenti CPU/GPU gratuiti aumentano la parte inclusa; quelli a pagamento aumentano
la quota assegnata ma mantengono la soglia inclusa precedente e autorizzano extra
quota alle tariffe ordinarie tramite crediti. Le nuove quote ridotte si applicano
ai nuovi job; i job già ammessi conservano il contratto congelato. Lo storage
segue capienza assegnata e intervallo di assegnazione, con eventi storicizzati.
Le variazioni di questa schermata riguardano il periodo corrente; non modificano
il listino dei piani per i rinnovi.

La cessazione admin è immediata, con una conferma. Il canone corrente viene
proporzionato al **tempo trascorso nel periodo**, senza azzerare o cancellare
accounting/extra quota. Se billing utente o servizio abbonamenti sono disabilitati,
il canone finale è zero. Un canone già pagato produce un importo da rimborsare,
visibile nello storico: il rimborso monetario è da regolare dal gestore tramite
il provider; non viene trasformato in crediti extra quota e non è eseguito
silenziosamente dalla cessazione. Rinnovi e piano successivo vengono rimossi.

Administrators can amend current CPU/GPU/storage limits up or down without resetting
the period or usage. Free versus paid increases are explicit. Paid compute remains
credit-funded overage, not additional free allowance. Existing admitted jobs retain
their terms; amendments apply to future admissions. Storage retains time-sliced
allocation evidence. Amendments do not rewrite the plan catalog for renewal.
Immediate termination prorates the current base fee by elapsed period time, only
when subscription service and user billing are enabled; overage history remains.
Already paid differences are recorded as operator refund liabilities, not wallet
credits or automatic provider refunds.

## PayPal: configurazione e collaudo / Configuration and acceptance

1. In PayPal Developer creare un'app REST per l'ambiente **Sandbox** e annotare
   Client ID e Client Secret. Separare rigorosamente credenziali Sandbox e Live.
2. Configurare un webhook HTTPS pubblico:
   `https://mta.apps.desalvo.eu/api/billing/paypal/webhook`, con eventi
   `PAYMENT.CAPTURE.COMPLETED` e `PAYMENT.CAPTURE.REFUNDED`. Annotare il Webhook ID.
3. Impostazioni admin → Abbonamenti e crediti → PayPal: scegliere ambiente,
   inserire i tre valori e abilitare. Le credenziali sono sigillate dal meccanismo
   del server e non ritornano nelle API; i campi vuoti mantengono il valore salvato.
4. L'utente paga il canone dovuto del contratto corrente dal profilo; compra i
   tagli di crediti configurati dalla pagina crediti. I crediti richiedono
   abbonamento/promo attivo, permesso utente e servizio crediti abilitato.
5. Il server definisce l'importo in EUR e usa Orders v2 CAPTURE con idempotenza.
   Un redirect di ritorno non accredita nulla: il server verifica ordine, identità,
   valuta, importo e catture completate. Webhook verificati tramite API PayPal;
   l'ordine canonico viene riletto dal server. Retry/callback duplicati non
   duplicano crediti o saldi. Rimborsi dei crediti verificati stornano il wallet.
6. I canoni sono debiti separati dai crediti extra quota; pagare un canone non
   carica il wallet. I pagamenti implementati sono **singoli**, non autorizzano
   addebiti automatici PayPal a ogni rinnovo. Le differenze di arrotondamento al
   centesimo sono conservate come saldo da regolare quando necessario.
7. Prima di Live, provare in Sandbox: acquisto crediti, saldo canone, doppio
   callback, annullamento, cattura in sospeso, importo/valuta errati e rimborso.
   Poi ripetere con webhook raggiungibile attraverso HAProxy. Nessuna transazione
   reale o configurazione del server dell'utente è stata eseguita in questo ciclo.

PayPal uses separate Sandbox/Live REST credentials plus a verified HTTPS webhook.
Enable it in the collapsible admin payment section. The current subscription fee
is payable from the profile; overage credits from the credit shop. Server-quoted
EUR amounts, merchant configuration, canonical order/capture identity and completed
payment state are checked before idempotent fulfillment. Signed/verified refund
events reverse credit top-ups. Current implementation is one-off checkout,
**not automatic recurring PayPal billing**. Sandbox and real ingress acceptance
remain required; no live money was moved during development.

Fonti / Primary sources:
[Orders v2 integration](https://developer.paypal.com/api/rest/integration/orders-api),
[standard checkout](https://developer.paypal.com/checkout/put-it-all-together/),
[webhook verification](https://developer.paypal.com/api/webhooks/v1).

## Ripetere le prove / Reproduce validation

Con le dipendenze runtime e Playwright/Chromium installati:
`python scripts/validate_playback_preparation.py`. La prova crea un server locale
con dati temporanei, otto tracce di 30 secondi, verifica scheduling sorgenti/cache
e pannello riverbero, poi termina il server e rimuove i dati. Scrive il rapporto
in `validation/r210-playback-browser-result.json`; non usa account dell'istanza
reale e non invia pagamenti. I tempi variano con hardware e carico.

With runtime dependencies and Playwright/Chromium installed, run the same command.
It starts a disposable loopback-only server, exercises eight edited audio tracks
and the built-in reverb panel, writes timings and assertions, then removes its
test data. It does not reuse production accounts or send payments.
