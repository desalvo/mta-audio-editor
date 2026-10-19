# r210 — continuità C++ e disinstallazione VST3 / C++ continuity and VST3 removal

## Italiano

Versione invariata: **0.3.0-r210**. Baseline verificata: `MTA-0.3.0-r210-vst3-progress-cpp-live-controls-cumulative.zip`, SHA-256 `42fe3889ec2b1affce9de31e2f678716991efa451bee157112c95f9c8e4b21c6`. Tutti i suoi 2.186 file vengono conservati nel cumulativo.

### Audio continuo

Il precedente percorso web C++ richiedeva e accodava ogni piccolo blocco PCM dal thread dell'interfaccia. Il margine corto, i ritardi HTTP e le operazioni grafiche potevano interrompere lo scheduling; inoltre il margine minimo di scheduling poteva introdurre vuoti fra blocchi già pronti.

Ora un Worker dedicato esegue richieste autenticate, controlla sequenza, posizione, dimensioni e finitezza dei campioni, e trasferisce i buffer direttamente a un AudioWorklet tramite MessageChannel. Una FIFO stereo limitata alimenta continuamente i quanti audio: il rendering non dipende dai timer o dalle risposte del thread grafico. Il riempimento iniziale e il lookahead sono contenuti e adattivi (obiettivo iniziale 350 ms; fino a 1,2 s su richieste lente, più un blocco massimo). Questo compromesso privilegia la continuità rispetto alla latenza minima osservata nella prova LAN precedente. In condizioni di rete insufficienti il sistema non inventa campioni o rallenta il contenuto musicale: il contatore di underrun segnala l'esaurimento della coda.

Un handshake identifica ogni reset e generazione della coda, impedendo che risposte tardive vengano riprodotte dopo seek, pausa o chiusura. La pausa è immediata sul sink; le richieste in corso vengono concluse prima di riallineare la sequenza server. Alla fine o a Stop vengono liberati worker, porte, nodo e sessione. Il clock del transport e i VU seguono i campioni effettivamente consumati. Mixer, gain, pan, mute/solo e insert mantengono gli aggiornamenti live.

Quando la frequenza del progetto differisce da quella dell'AudioContext, il sink usa un ricampionatore polifase sinc/Blackman a 64 coefficienti e 1.024 fasi, con filtro anti-aliasing. Alla stessa frequenza il percorso è bit-exact. Le prove includono 44,1/48/96 kHz, EOF e tagli dei pacchetti non allineati al quanto audio. Nei browser privi di AudioWorklet rimane il percorso AudioBufferSource, con lookahead maggiore e senza introdurre artificialmente un margine fra blocchi contigui; questo fallback dipende ancora dal thread UI.

Il decoder del grafo mantiene il cursore per letture consecutive anziché effettuare un seek a ogni blocco. Un controllo su MP3 stereo di 30 s ha eliminato 2.813 seek e prodotto campioni identici. I tempi del microbenchmark (0,1569 s prima e 0,1630 s dopo, nello stesso ambiente) non dimostrano un incremento prestazionale: la modifica evita chiamate superflue senza alterare il segnale.

### Play/Pausa

La chiusura dell'indicatore di preparazione sovrascriveva lo stato del pulsante già impostato dal motore. Il controllo ora viene riallineato allo stato effettivo e usa una Pausa SVG esplicita con due barre, tooltip ed etichetta accessibile coerenti. Avvio, pausa, ripresa e Stop sono verificati anche con i bridge nativi. Il tasto Spazio continua a usare lo stesso comando Play/Pausa.

### Disinstallazione

Nello stesso catalogo VST3 ogni pacchetto installato presenta **Disinstalla**, con una sola conferma e la possibilità di eliminare anche sorgenti e cache di compilazione. La rimozione riguarda tutto il pacchetto (ad esempio tutti e quattro i Dragonfly). L'interfaccia avvisa dei progetti che lo referenziano; tali progetti rimangono intatti e richiederanno una reinstallazione o la rimozione degli insert interessati.

I controlli admin sono applicati sia alla pianificazione sia alla POST di rimozione. Sono accettati solo ID del catalogo; non sono accettati percorsi arbitrari. La rimozione viene bloccata durante un'installazione concorrente, con sessioni live interessate o con un editor desktop indipendente aperto. Un registro debole delle sessioni copre server, trasporto nativo, editor live e monitoring MIDI. I lock proteggono l'avvio dell'host rispetto alla rimozione.

Il pacchetto viene staccato atomicamente sullo stesso volume, anche con un mount dedicato. Le directory di transizione sono escluse dalla discovery e dall'esecuzione. La cancellazione non segue collegamenti simbolici verso altri dati; root, pacchetto e cache vengono verificati. I file VST3 installati fuori dal catalogo e gli effetti DSP interni non vengono rimossi da questa funzione.

### Risultati verificati

- Regressione estesa: **4.187 passati, 35 saltati, 10 esclusi per socket/agente indisponibili**, nessun fallimento. Configurazione test CI `MTA_ALLOW_INSECURE_NO_AUTH=true`; i probe server/browser disabilitano esplicitamente tale modalità e usano una sessione autenticata.
- **16 nuove regressioni finali passate**, compresi i controlli aggiunti dopo l'avvio della regressione estesa; 23 controlli continuità/preparazione passati; 42 test con CHOW Tape reale passati (uno escluso senza display).
- Server ASGI, Chromium, WebAudio e C++ reali, otto tracce: avvio sessione 1,239 s, cambiamento volume osservato sul flusso udibile dopo 0,538 s, zero errori JS e zero underrun. Rete irregolare (ritardi iniettati fino a 180 ms) e cinque blocchi UI da 450 ms: **zero underrun**, Play/Pausa e mixer passati; risposta volume 0,701 s nella prova con rete rallentata.
- Motore corrente: probe reale passato, nessun render backend aggiuntivo, nessun errore JS, editor/bozze preservati. Avvio 2,198 s e riavvio cache 0,265 s nell'ambiente impegnato dalle regressioni.
- Rimozione: permessi, conferma, riferimenti ai progetti, sessioni/editor attivi, cache conservata o cancellata, tentativi di traversal e symlink, installazione concorrente e directory di transizione verificati. I progetti di prova sono confrontati prima/dopo la rimozione.
- Ruff, Bandit alle soglie CI, license guard, sintassi JS e pip check passati. Il plugin reale di prova è scaricato a checksum bloccato fuori dal progetto: nessun binario esterno è redistribuito.

Rapporti in `validation/r210-continuity-*`, `r210-continuous-pcm-*`, `r210-uninstall-final.xml` e `r210-decoder-contiguous-reads.json`. Probe ripetibile: `python scripts/validate_cpp_live_controls.py --core /percorso/libmta_audio_core.so --stress`. Prova campioni: `node tests/server_pcm_continuity.cjs`.

Restano l'accettazione sul server reale Rocky/HAProxy e l'ascolto sui dispositivi/browser fisici, inclusi Windows e macOS. I test locali non costituiscono certificazione della produzione o garanzia di latenza su qualsiasi rete. Nessun commit, push, tag, release o intervento su server reali.

## English

Version remains **0.3.0-r210**; all 2,186 baseline files are retained.

Server PCM fetching and validation now run in a dedicated Worker. Transferable buffers reach a bounded AudioWorklet FIFO through a MessageChannel, so main-thread GUI stalls no longer schedule the audio. Startup and lookahead adapt to observed request times. Pausing/seek uses generation-tagged reset acknowledgements and waits for outstanding pulls before resetting server sequence state. Playback position/meters follow consumed samples; late chunks cannot restart a stopped or replaced stream. Workers, ports and sessions are released on Stop/EOF.

A 64-tap, 1,024-phase sinc/Blackman resampler handles different project/output sample rates with anti-aliasing. Equal-rate packet boundaries are bit-exact. The older-browser fallback remains available with safer lookahead and contiguous scheduling, but still depends on main-thread scheduling. Consecutive decoder reads avoid redundant seeks; the MP3 microbenchmark demonstrated identical output and fewer calls, not a speed increase.

The preparation indicator no longer overwrites the running transport state. An explicit two-bar SVG, localized tooltip and accessible label identify Pause. Play/Pause/Resume/Stop and Space are verified.

Installed managed VST3 cards now offer Uninstall, one confirmation and optional source/build-cache cleanup. Stored project references are reported and preserved. Administrator authorization, allowlisted IDs, path/symlink guards, live-host/editor exclusion, concurrent-install exclusion and atomic same-volume detachment protect removal. Transitional folders cannot be discovered or executed. Independently installed system plugins and built-in DSP effects remain outside this action.

Final extended regression: **4,187 passed, 35 skipped, 10 unavailable host-agent socket cases excluded**, no failures. All **16 final new regressions** passed, including additional controls after the extended run began; 42 real-CHOW tests passed with one display-dependent skip. Actual ASGI/Chromium/WebAudio/C++ tests on eight tracks observed zero underruns, including injected network delays up to 180 ms and five 450 ms GUI stalls. Normal session startup was 1.239 s and the audible fader response 0.538 s; the stressed fader response was 0.701 s. The original engine/editor-preservation probe also passed. Physical devices and the real Rocky/HAProxy deployment still require acceptance. No Git publication or production modifications were performed.
