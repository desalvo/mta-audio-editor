# r210 — DiffSinger ONNX, Deep reale e confronto YourMT3

21 ottobre 2026 · versione **0.3.0-r210** invariata. Stato successivo a `R210_REAL_RUNTIME_HANDOFF_IT_EN.md`. Nessuna operazione Git o intervento sui server reali.

## Italiano

È stato chiuso il collegamento software mancante con una banca DiffSinger effettivamente disponibile: **Qixuan 2.7.0**, esportata per OpenUtau in ONNX, con vocoder comunitario PC-NSF-HiFiGAN 2025.02. Sono riuscite inferenze reali CPU dal bridge MTA, con vocali esplicite, testo inglese «hello world» e melisma. Il WAV vocale generato è stato ritrascritto realmente da YourMT3 PS, che ha rilevato le note **60, 64, 67** e la classe vocale corretta.

Anche la modalità Deep ha eseguito l'intero percorso locale di produzione: **Demucs → quattro YourMT3 → tre Basic Pitch → riconciliazione**, con processi reali, artefatti validati, misura CPU e checkpoint di ripresa. Nessuna fixture sostituisce queste inferenze.

**Non è però certificata la conclusione integrale del requisito di trascrizione accurata a dieci–sedici strumenti:** il mix tecnico difficile già incluso continua a non superare il confronto. Dieci parti prodotte da Deep PS non equivalgono a dieci strumenti correttamente identificati. Questo limite non viene attribuito all'hardware dell'utente né nascosto da una regressione software verde.

### Modifiche effettive

- `diffsinger_onnx.py`: modello acustico ONNX end-to-end e vocoder originali, senza conversione/modifica dei pesi; verifica dell'intero inventario, SHA-256 e dimensioni; compatibilità fra metadati acustici/vocoder; token e language ID per fonemi condivisi fra lingue; durate su un unico clock cumulativo; F0 della partitura e curve dichiarate; sessioni ORT CPU limitate, telemetria disabilitata prima dell'import e nessuna libreria di operatori personalizzati. Esportazione mono 48 kHz con resampling e headroom esplicito.
- Il registro gestito ora distingue `native` da `openutau-onnx`. Restano obbligatori componenti, inventari, licenze separate per cantante/vocoder e controllo dell'interprete. Il vecchio percorso `.ckpt` OpenVPI è conservato. Il supporto ONNX riguarda l'interfaccia verificata, non qualsiasi esportazione arbitraria.
- Il builder `scripts/build_qixuan_onnx_bundle.py` accetta soltanto i due archivi originali fissati, conserva **tutti i 37 file originali** di banca e vocoder e aggiunge il profilo inglese e l'evidenza del motore MTA. Non scarica, non esegue modelli, non attiva autorizzazioni. Il pacchetto generato è installabile dal gestore modelli e rimane **disabilitato**.
- Il profilo inglese gestisce i segni IPA di lunghezza delle vocali; la durata effettiva resta controllata dalla partitura. Sono testati testo inglese e melisma. IT/FR e altre banche richiedono profili compatibili e revisione linguistica specifica: non sono dichiarati certificati per questa banca.
- `scripts/install_studio_yourmt3_ps.py` aggiunge il checkpoint PS ufficiale a un runtime noPS già verificato. Default noPS, sorgenti, interprete, receipt e pesi precedenti restano invariati. Conversione **weights_only=True**, 655 tensori / 47.081.642 elementi, medesimi vincoli stretti; receipt PS distinto, `tested=true` soltanto dopo vera inferenza non vuota. Nessun uso di `weights_only=False` o autorizzazione di classi modello pickle.
- Corrette le classi vocali YourMT3 **100/101**: significano voce/coro nel vocabolario del modello, non programmi GM FX. Il risultato mantiene `singing-voice`/`singing-chorus`; 53/52 sono programmi GM di riproduzione **generati**, dichiarati come tali. I programmi restanti rappresentano le classi del modello, non una classificazione fine garantita di tutti i 128 timbri GM.
- La ripresa Deep include nell'impronta anche revisione e pesi del nuovo cache Hugging Face di Demucs 4.1, oltre al percorso legacy `.th`. Una sostituzione dei pesi attivi invalida i risultati recuperabili; i normali link verso blob HF sono ammessi soltanto dentro il repository.
- Il benchmark non può più superare il target contando parti spurie: richiede almeno una corrispondenza uno-a-uno di pitch, programma, onset e offset per ciascuno strumento identificato. Le parti senza strumento assegnato non contribuiscono. Precision/recall/F1 restano necessarie per valutare l'accuratezza complessiva.

### Risultati reali e limiti

| Prova sul mix tecnico originale | Parti effettive | Strumenti etichettati nel confronto | Note | Match esatti | F1 |
|---|---:|---:|---:|---:|---:|
| YourMT3 noPS, ciclo precedente | 5 | 5 | 7 | 1 | 0,117647 |
| YourMT3 PS | 3 | 3 | 6 | 1 | 0,125000 |
| Deep con noPS | 9 | 7 | 45 | 1 | 0,036364 |
| Deep con PS, primo confronto | 10 | 7 | 43 | 1 | 0,037736 |

Il riferimento contiene dieci programmi GM e dieci note simultanee note a priori; è sintesi FluidR3 MIT, **non una registrazione musicale rappresentativa**. I confronti usano onset 50 ms, offset 100 ms e programma GM esatto. Le classi rappresentative del modello non coincidono con tutte le varianti GM; il test fine resta conservato e non viene riclassificato retroattivamente per farlo passare. Questi risultati non autorizzano una promessa universale di dieci strumenti, né una confidenza calibrata. La ripetizione Deep finale e il relativo replay sono riportati separatamente nei JSON, poiché la separazione può variare fra esecuzioni.

Il replay di **otto stadi realmente calcolati** è stato verificato con un callback che vieta nuove esecuzioni: stesso risultato, nessuna nuova inferenza e `usage={}`. È una prova di recupero di risultati reali, non una nuova inferenza né una fixture musicale.

Il nuovo percorso Qixuan usa durate e F0 della partitura. Le curve di breathiness/voicing predefinite (-48/-12 dB) sono **controlli espliciti del profilo**, riportati nei metadati; non vengono spacciate per predizioni di un modello di varianza. Pronuncia, naturalezza, timbro ed espressività vanno ascoltati. La banca completa include anche i modelli di durata/pitch/varianza originali, conservati ma non dichiarati eseguiti dal nuovo runner.

### Provenienza, licenze e pacchetti

- Qixuan: [release originale 2.7.0](https://github.com/yqzhishen/qixuan-diffsinger/releases/tag/v2.7.0), archivio 420.707.627 byte, SHA-256 `fe8ee7c95883d327a2b7facbbe832a7a53e1344918dc791ca83fc23b08034110`. Le [condizioni originali cinesi](https://github.com/yqzhishen/qixuan-diffsinger/blob/main/terms_of_use/Terms_of_Use.zh-CN.md) prevalgono: pacchetto completo, attribuzione a **绮萱 / Qixuan**, indicazione **DiffSinger** e sintesi AI, nessun servizio di inferenza a pagamento. Nessuna concessione commerciale viene inventata.
- Vocoder: [OpenVPI Community Vocoders](https://openvpi.github.io/vocoders/), PC-NSF-HiFiGAN 2025.02, archivio `.oudep` 52.760.610 byte, SHA-256 `ba7d43142d41f6900c8264b5662ca7125a50feb8760bb8b9615c61a8f5e6902e`, **CC BY-NC-SA 4.0**, avvisi originali inclusi. La gratuità da sola non rende consentito dalla licenza NC un servizio di natura commerciale: la destinazione del servizio va verificata separatamente.
- YourMT3 PS: [pubblicazione originale dell'autore](https://huggingface.co/mimbres/YourMT3/tree/e45ebd70398682d54b7bb1901a5216e18f3b1824), Apache-2.0, checkpoint 758.957.292 byte, SHA-256 `7427055b51c3c8c86f6a35493cf0741d8db29186052055b59193590a82e6ec01`; safetensors verificato `bbc302a9f3d0189259140a81d20eff53d4b5523884ccb9bcd5149042e95fa698`.
- Demucs: pubblicazione dell'autore [adefossez/HTDemucs](https://huggingface.co/adefossez/HTDemucs/tree/cbc8a9b1a87023b7fd74e7b3412e6321c0eab003), revisione fissata e hash nel receipt. Modello `955717e8.safetensors`, 84.025.440 byte, SHA-256 `d9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd`; codice Demucs MIT. Nessun fallback di download è servito durante le inferenze registrate.
- Basic Pitch: modello ONNX Spotify 0.4.0, SHA-256 originale `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`, Apache-2.0. Installazione, self-test e inferenze Deep effettivi. **Pip check segnala TensorFlow assente nei metadati upstream**, benché il backend eseguito sia ONNX: TensorFlow non è stato scaricato inutilmente e i metadati non sono stati alterati per nascondere l'avviso. Gli ambienti Demucs/conversione e YourMT3 passano pip check; freeze e log separati inclusi.
- eSpeak NG: runtime GPL opzionale esterno per il G2P; non viene incorporato nel cumulativo sorgenti o nei pesi della banca.

Il cumulativo sorgenti non incorpora pesi, venv o cache. Il pacchetto gestito Qixuan/vocoder è consegnato **separatamente e completo**, con hash, senza autoattivazione o attestazioni inventate. Le policy commerciali/non commerciali e le conferme richieste dall'applicazione restano operative.

### Passaggio ai collaudi

Seguire `R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md` per installazione controllata, variabili, selezione PS, verifica delle licenze e prove locali. Restano i test sul browser reale (Chromium non scaricabile qui), trasporto Unix consentito sul target, dispositivi/ASIO/VST/GPU, ascolto e pronuncia. Rimane inoltre **aperto il requisito qualitativo dieci–sedici strumenti**: servono valutazione di modello/strategia e registrazioni autorizzate con riferimenti indipendenti; un cambio hardware non prova che questo requisito sia soddisfatto. Non è dichiarata la chiusura completa di tutte le tre macroaree.

## English

A complete author-published Qixuan 2.7.0 bank and matching community ONNX vocoder now run through MTA's new pinned ONNX bridge, preserving every original model/package byte. Real CPU vowel, English-text and melisma synthesis passed. The generated vocal was actually transcribed by YourMT3 PS as singing voice, pitches 60/64/67. Singing classes 100/101 are now kept distinct from GM FX programs; 53/52 are explicitly generated playback proxies.

Real local production Deep execution ran Demucs, four YourMT3 passes, three Basic Pitch passes and reconciliation, with validated artifacts and CPU metering. Eight genuine stage results were replayed without new execution or new usage. HF Demucs checkpoint revisions/weights now invalidate stale recovery. The original-author PS variant installs beside noPS using strict tensor-only conversion and a separate tested receipt. The benchmark target now requires actual matched instruments rather than a bare count of predicted parts.

**Full three-area completion is not certified.** Both YourMT3 variants and both Deep combinations failed the existing dense ten-program exact-GM stress test; ten predicted parts are not ten correct instruments. Recorded-music quality remains an open model/strategy gate, not a hardware-only acceptance item. Qixuan English/vocalises are verified; other language/bank profiles need their own review. Real browser, IPC, physical audio, native plugin/OS and GPU acceptance remain target checks.

The supplied managed bank remains disabled. Qixuan requires a complete free distribution/service channel, attribution and AI/DiffSinger labeling; the vocoder is CC BY-NC-SA 4.0. No commercial rights or operator confirmations were fabricated. Basic Pitch's upstream metadata still reports missing TensorFlow, while the real ONNX path works; unused TensorFlow was neither downloaded nor hidden by edited metadata. Source archive/version, legacy AI, VST SDK, existing files and tests are preserved; no Git or production actions.

## Verifica finale / Final verification

Regressione generale: **4.608 passed, 0 failed, 80 skipped, 6 warnings**, 524,10 s. Gli 80 skip mantengono i requisiti reali di piattaforma, browser, plugin, hardware o modelli opt-in: non sono pass. L'ultima correzione della classe vocale, successiva alla raccolta della suite generale, è coperta dai **68 test mirati passati** e dalla vera ritrascrizione del canto Qixuan; i conteggi non si sommano. Ruff superato.

Il primo tentativo generale si è interrotto per spazio temporaneo esaurito (exit 120), conservato come tale; la ripetizione completa è riuscita con le normali opzioni pytest di ritenzione delle directory temporanee. Nessun test eliminato. Il replay finale recupera otto stadi, risultato identico, zero nuove inferenze e nessun nuovo consumo contabilizzato. Il confronto finale Deep è in `validation/r210-closure-deep-current-quality.json`: il target rimane non raggiunto.

No Git operation or production-server change was performed. Source and model archives are separate; the complete model bundle stays disabled until genuine operator policy review. Software integration has advanced substantially, but the failed multi-instrument quality gate remains an unresolved model/quality requirement, not a target-hardware acceptance item.
