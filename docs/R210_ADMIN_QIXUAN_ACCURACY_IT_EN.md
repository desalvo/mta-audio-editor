# MTA Audio Editor 0.3.0-r210 — amministrazione, Qixuan IT/FR e accuratezza

21 ottobre 2026. Versione invariata. Nessun commit, push, tag, release o intervento sui server reali.

## Esito italiano

Le correzioni software di navigazione tariffaria, gestione selettiva dei file AI e profili Qixuan IT/FR sono implementate e verificate. **L'obiettivo complessivo di accuratezza su 10–16 strumenti non è raggiunto. Non restano esclusivamente collaudi hardware.** I risultati negativi dei modelli reali sono conservati, senza sostituirli con fixture, cambiare riferimento o allargare le tolleranze.

### Cosa cambia

- **Abbonamenti e crediti:** il collegamento resta utile e porta a `/admin/ai-billing#tariffs`; il vecchio `/ai-billing` reindirizza con protezione amministrativa. Le tariffe centralizzate sono usate nel consumo/fatturazione e nelle eccedenze dei piani: non vengono duplicati listini o cambiati prezzi.
- **Impostazioni → Modelli AI:** inventario raggruppato per motore con ricerca, paginazione, membri presenti e mancanti, esportazione del singolo file, download da fonte fissata, ripristino SHA e cancellazione selettiva. Include modelli gestiti, runtime YourMT3/MR-MT3, cache HF, percorsi DiffSinger configurati, encoder/vocoder e modelli legacy. Sono fissate 129 fonti. Restano i controlli amministrativi, le licenze, i lock dei job e la protezione dei blob condivisi. I file privati/gated o convertiti senza URL degli stessi byte richiedono ripristino esatto o ricetta di installazione; non viene inventato un download universale. Le librerie generiche dei venv e i server remoti non configurati non sono checkpoint amministrabili qui. [Dettagli](MODEL_ADMIN_ASSETS_R210_IT_EN.md).
- **Qixuan:** profili separati EN/IT/FR, mapping verificati, fonemi espliciti con prefissi reali, melismi e vocalizzo predefinito `A→en/aa`. UI e receipt espongono lingua, SHA del profilo e approssimazioni. IT/FR usano una **proiezione sui fonemi EN/JA/ZH esistenti**, non modelli addestrati nativamente per queste lingue. [Implementazione, prove e istruzioni](R210_QIXUAN_IT_FR_IMPLEMENTATION_IT_EN.md).
- **MR-MT3 opzionale:** backend separato con selezione esplicita, runtime verificato, cache, policy e billing integrati. Caricamento del checkpoint originale esclusivamente `weights_only=True`, struttura/dimensione/SHA fissati e conversione Safetensors con tutti i 193 tensori originali identici. Decoder con identità GM, tie, finestre e durate limitate alla sorgente; correzione dell'ultimo hop parziale. Nessuna sostituzione automatica di Accurate/Deep. La variante con memoria è solo ricerca isolata, non un nuovo default.
- Il cumulativo conserva tutte le precedenti correzioni di AI Vocal Studio, Audio-to-MIDI, General MIDI, legacy AI, SDK VST, sorgenti, test e documentazione. I modelli non vengono abilitati automaticamente e i pesi originali non vengono modificati.

### Verifica conclusa

**Regressione generale: 4.680 passed, 0 failed/errors, 98 skipped, 6 warnings, 540,37 s, exit 0.** Log e JUnit: `validation/r210-admin-language-general.*`. Il precedente tentativo interrotto è etichettato `pre-freeze-interrupted` e non è conteggiato come riuscito. Controlli mirati amministrazione/lingue: 70 passed; Qixuan: 82 passed/3 skipped. Questi conteggi si sovrappongono alla regressione generale e **non si sommano**. Ruff, compilazione e sintassi JavaScript superati.

Gli skip riguardano anche prerequisiti ambientali riproducibili (Playwright, WeasyPrint, configurazioni GM/runtime, libreria eSpeak nel venv generale), oltre a VST, Win32, audio reale e socket Unix vietati nell'ambiente. Tutte le ragioni sono nel riepilogo JSON. Le tre prove G2P saltate nel venv generale sono affiancate da 78 parole e otto inferenze reali nell'ambiente Qixuan isolato; non diventano per questo `passed` nel conteggio pytest. Le verifiche GM/VST reali di cicli precedenti rimangono evidenza storica, non vengono presentate come nuove esecuzioni.

| Esecuzione reale | Risultato | Cosa dimostra |
|---|---|---|
| Qixuan eSpeak IT/FR | 78 parole, zero fonemi sconosciuti | Copertura del corpus; non perfezione linguistica universale |
| Qixuan acustico + vocoder ONNX CPU | 8/8 casi, 32 passi, 46,538 s totali | Audio finito, non silenzioso, 48 kHz mono PCM24, durata entro 25 ms |
| Fonemizzazione nel processo Studio principale | 2/2 casi IT/FR con libreria eSpeak già installata | Il percorso parent funziona oltre al runner isolato |
| MR-MT3 baseline originale | 5 parti, 13 note, 0 match esatti, F1=0; 6,520 s | Runtime funzionante; benchmark a 10 strumenti fallito |
| MR-MT3 con memoria originale | 4 parti, 7 note, 0 match esatti, F1=0; 1,786 s | Inferenza su due finestre con memoria reale; benchmark fallito |

Il riferimento tecnico a dieci strumenti è lo stesso WAV di 3,5 s e lo stesso JSON iniziali, byte per byte, prodotto in precedenza con FluidR3. Il matching considera programma GM, pitch, onset entro 50 ms e offset entro 100 ms. È uno stress test tecnico sintetico, non un corpus rappresentativo di musica registrata. I precedenti YourMT3/Deep restano sotto obiettivo; i nuovi risultati non giustificano alcuna certificazione positiva o conclusione universale sull'incapacità dei modelli. Un ulteriore prototipo Slakh non viene promosso in produzione senza evidenza positiva e configurazione coerente.

### Dipendenze Qixuan e controllo automatico

Il blocco iniziale proveniva dal revisore automatico delle autorizzazioni di esecuzione dell'ambiente, che aveva applicato il precedente vincolo di sola ricostruzione ZIP; non era un controllo interno MTA/Qixuan né un errore del modello. L'autorizzazione successiva dell'utente all'installazione è stata recepita. Ambiente Qixuan isolato, ONNX Runtime 1.31.0, espeakng-loader 0.2.4 e dipendenze installati, `pip check` pulito; prove reali concluse. L'agente non ha disattivato o aggirato il revisore. Non occorre rimuoverlo per le prove completate.

### Pacchetti e riproduzione

Il cumulativo sorgenti contiene codice, documentazione, test, log, audit e gli otto WAV Qixuan con attribuzioni. Non incorpora venv, cache o nuovi checkpoint di ricerca. Il bundle Qixuan completo è separato:

- `MTA-Qixuan-2.7.0-onnx-IT-EN-FR-release-v2-bundle.zip`, **474.464.355 byte**.
- SHA-256 **f02ee089e85d58ca7ca7caff4d1e3d5ab508375d315ddcc0f0f5db8d19f1c4ac**.
- CRC completo, inventario SHA e conservazione byte per byte dei **37 membri originali** verificati. Asset disabilitato in attesa della revisione effettiva dell'operatore; condizioni originali incluse.

Per la fonemizzazione automatica, eSpeak NG deve essere accessibile **anche al processo Studio principale**, non soltanto al Python del runner. Installare `espeakng-loader==0.2.4` nell'ambiente principale oppure configurare `MTA_ESPEAK_LIBRARY` e `MTA_ESPEAK_DATA` con percorsi assoluti alla libreria e ai dati già installati. La prova effettiva di questa seconda opzione è in `validation/r210-qixuan-itfr-parent-g2p.json`.

Il nuovo runtime MR-MT3 è opzionale. Creare un venv con `python -m venv --copies`, installare le ruote CPU torch/torchaudio dal sito ufficiale e `requirements-studio-mrmt3.txt`, quindi usare `scripts/install_studio_mrmt3.py --runtime <venv assoluto> --source-archive <ZIP fissato> --checkpoint-local <mt3.pth originale> --test-audio <WAV autorizzato> --accept-model-licenses`. Se si omettono gli archivi locali lo script usa soltanto le due fonti ufficiali fissate. Configurare `MTA_STUDIO_MRMT3_RUNTIME` e completare la vera ammissione delle licenze/policy: il self-test non la concede. Non installare l'intero wrapper con backend estranei.

Pin MR-MT3: wrapper `openmirlab/mt3-infer` commit `d8cbd287470291dee335f84315c5a9b9ff6e6c8a`; checkpoint `gudgud1014/MR-MT3` revisione `7bd24c3e1dc26468a6a9354c0a4f174405c9bad8`, `mt3.pth` SHA `b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f`. La ricerca con memoria usa il codice originale `826ea84a933f93cd707d11e91af711f1d19c8d79` e checkpoint SHA `d477dfb1f8bb7eecee54d996f68c7b9008d6ee2e84f62312d1826c60c8992f18`. Compatibilità e provenienza complete sono negli audit; caricamento sicuro e stato rigoroso, senza allowlist o chiavi ignorate. Licenze MIT/Apache delle componenti selezionate restano distinte.

### Attività ancora aperte

1. **Qualità software/modelli:** raggiungere e documentare l'accuratezza richiesta su 10–16 strumenti con un modello/corpus appropriato. Non è un collaudo rimandabile al solo hardware dell'utente; le inferenze qui eseguite hanno fallito il riferimento tecnico esistente. Non si garantisce una soglia cambiando routing, nomi o fallback.
2. **Qixuan:** ascolto e revisione linguistica IT/FR delle approssimazioni; una pronuncia nativa richiederebbe una banca nativa o un diverso addestramento, non il solo mapping.
3. **Target:** sistemi operativi effettivi, audio/MIDI, browser, VST/VSTi e SDK compilato, driver e GPU quando necessari; verifica dell'installazione e attivazione legittima degli asset sull'ambiente dell'utente.

Commit suggerito cumulativo su una sola riga in `COMMIT_MESSAGE_R210_ADMIN_LANGUAGE.txt`. Lo SHA esatto dell'ultimo commit dell'utente non è presente nell'archivio sorgenti: il messaggio riassume il lavoro cumulativo noto, non un diff Git certificato.

## English

Billing tariff navigation, engine-grouped per-file AI administration and pinned Qixuan EN/IT/FR profiles are implemented. **The requested 10–16-instrument accuracy target is still unmet; the remaining work is not exclusively hardware acceptance.** General regression: **4,680 passed, zero failures/errors, 98 skipped, six warnings, 540.37 seconds**. Focused counts overlap the general run. Skip reasons and actual evidence are preserved, including environmental/browser prerequisites and optional target tests.

Qixuan ran actual eSpeak for 78 IT/FR words and eight real CPU acoustic/vocoder ONNX cases, at 32 steps. Every waveform was finite, non-silent, mono 48 kHz PCM24 and within 25 ms of score duration. Two additional actual parent-process G2P cases verified access to the installed shared eSpeak library from Studio. IT/FR explicitly project onto existing EN/JA/ZH bank phones; native pronunciation quality is not claimed. The exact complete 474,464,355-byte bundle has SHA-256 `f02ee089e85d58ca7ca7caff4d1e3d5ab508375d315ddcc0f0f5db8d19f1c4ac`, passed CRC/inventory checks and retains all 37 original members unchanged. No automatic model activation or license grant occurs.

Both original MR-MT3 baseline and original memory-retaining MR-MT3 executed actual CPU inference with safely loaded, unmodified tensors and strict state loading. On the unchanged ten-program technical stress mix they produced respectively 5 parts/13 notes and 4 parts/7 notes, both with zero exact matches. This shows runtime feasibility and a failed specific accuracy gate, not universal model inability. The optional baseline backend is integrated without replacing existing Deep/Accurate defaults; the memory experiment remains isolated research. Model/corpus quality work is still required before the full software objective can be declared complete.

The central AI inventory supports fixed-source downloads, exact-hash restore, individual export/deletion and complete packages, retaining admin protection, job locks, shared-cache safety and license admission. Converted/private/gated files require their legitimate exact source or installation recipe; no arbitrary URL/path download is exposed. Source staging is not runtime installation. The tariff link remains useful and now reaches the canonical protected billing page.

The user's explicit Qixuan dependency-install authorization was applied, the isolated environment passed `pip check`, and real tests completed. The initial block came from the execution authorization reviewer, not MTA. No review bypass, Git operation or production server change occurred. Source ZIP, evidence, separate licensed Qixuan bundle and a compact one-line cumulative commit suggestion are supplied. Hardware/browser/plugin acceptance and linguistic listening remain distinct from the unresolved multi-instrument model-quality work.
