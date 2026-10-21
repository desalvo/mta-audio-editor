**Aggiornamento / Current closure:** [Qixuan IT/FR contextual G2P and runtime closure](R210_QIXUAN_IT_FR_CLOSURE_IT_EN.md). Le otto prove e il bundle v2 descritti sotto sono storici; usare il nuovo bundle context finale. / The eight cases and v2 bundle below are historical; use the final context bundle.

# Qixuan IT/FR — implementazione e prove reali / Implementation and real tests

21 ottobre 2026 · MTA Audio Editor **0.3.0-r210**, invariata.

## Italiano

### Cosa è stato sviluppato

- Profili fonetici Qixuan separati per **italiano, inglese e francese**, con binding per lingua, SHA-256 del checkpoint acustico, inventario e mapping IPA verificati. La banca originale contiene soltanto fonemi/modi acustici **en/ja/zh**: IT/FR sono dichiaratamente **proiezioni tra lingue**, non nuovi fonemi addestrati o una certificazione di pronuncia nativa.
- IPA normalizzato NFC, lunghezze vocaliche/consonantiche, geminate, palatali, vocali nasali e vocali anteriori arrotondate. I fonemi non presenti nel mapping vengono rifiutati esplicitamente. Le approssimazioni sono elencate nel profilo: tap giapponese per la vibrante italiana, l+y per la laterale palatale, r inglese per la rotica francese, rime nasali mandarine per le nasali francesi e `zh/ve` per alcune vocali arrotondate medie. Possono essere udibili accenti o code nasali: vanno ascoltati.
- Reali output eSpeak hanno esposto gli allofoni italiani ɪ/ʊ e i casi di semivocale/iato. Regole **letterali, limitate e tracciabili**, conservando gli accenti prima del mapping, gestiscono fra gli altri: ciao (1 nucleo), cuore (2), paura (3), gioia (2), mio (2), buongiorno (3), aiuto (3), nuit/lui (1). Non vengono rimossi automaticamente segni IPA non riconosciuti. Un allineamento musicale diverso si può correggere tramite fonemi espliciti e melismi, conservando la revisione umana.
- Corretto l'inserimento dei fonemi espliciti: sono ora accettati i prefissi reali `en/`, `ja/`, `zh/`, restando vietati spazi e controlli. I token vengono comunque verificati contro l'inventario realmente fissato della banca; non vengono passati come comandi.
- Corretto il vocalizzo predefinito dell'interfaccia: `A` X-SAMPA viene risolto dal mapping fissato in `en/aa`. Le altre vocali dichiarate hanno associazioni esplicite; simboli sconosciuti falliscono, senza inventare fonemi.
- Interfaccia web/native, catalogo e receipt dichiarano la proiezione. Con questa banca, IT/FR in modalità inizialmente `native` selezionano il profilo automatico eSpeak; le scelte esplicite restano controllate. Il receipt registra lingua, modalità, approssimazioni, regole, metodo effettivo e SHA del profilo. Gli avvisi del risultato accompagnano il materiale generato.
- Builder da due archivi originali o upgrade dal **precedente bundle completo esatto e fissato**. Tutti i **37 membri originali** della banca/vocoder sono conservati byte per byte, inclusi modelli, configurazioni, immagini e avvisi. Non viene modificato alcun peso. Il nuovo asset ha ID distinto `qixuan-2-7-onnx-it-en-fr-r210`, così può coesistere con il precedente.

### Pacchetto completo verificato

`MTA-Qixuan-2.7.0-onnx-IT-EN-FR-release-v2-bundle.zip`

- Dimensione: **474.464.355 byte**.
- SHA-256: `f02ee089e85d58ca7ca7caff4d1e3d5ab508375d315ddcc0f0f5db8d19f1c4ac`.
- CRC ZIP completo, tutti gli SHA/dimensioni dei membri, confronto dei 37 originali e corrispondenza dell'evidenza del motore ai sorgenti finali verificati.
- Il bundle resta **disabilitato**. Installazione e prove non concedono licenze, non modificano le policy e non fabbricano l'approvazione dell'operatore. Le condizioni originali Qixuan e del vocoder restano incluse. Il cumulativo sorgenti non incorpora pesi o venv.

### Esecuzioni effettive

Ambiente isolato Python 3.12, NumPy 1.26.4, SciPy 1.17.1, ONNX Runtime 1.31.0, espeakng-loader 0.2.4; **pip check pulito**. Le dipendenze sono state installate soltanto dopo la nuova autorizzazione esplicita dell'utente alle prove Qixuan. Nessun fallback verso servizi remoti.

- **78 parole IT/FR** passate realmente per eSpeak NG e per l'inventario fissato, senza fonemi sconosciuti: corpus e IPA effettivi sono nei due JSON `r210-qixuan-itfr-real-g2p*.json`. Questo misura copertura tecnica del corpus, non perfezione linguistica universale.
- **Otto inferenze neurali CPU reali**, dal bridge MTA tramite runner offline, modello acustico e vocoder ONNX originali, **32 passi**. Nessuna fixture sostituisce le inferenze. Output mono 48 kHz PCM 24-bit, finiti e non silenziosi, durata entro 25 ms dalla partitura. Gli hash audio e i fonemi effettivamente allineati sono nell'audit.

| Caso | Lingua | Note | Durata WAV (s) | Picco | Wall time (s) |
|---|---|---:|---:|---:|---:|
| it-text | it | 4 | 2.403271 | 0.5746 | 6.090 |
| it-palatals | it | 3 | 1.811167 | 0.6432 | 5.404 |
| it-melisma | it | 5 | 3.007000 | 0.6079 | 6.301 |
| fr-text | fr | 3 | 1.811167 | 0.6181 | 5.336 |
| fr-nasal-rounded | fr | 3 | 1.811167 | 0.5084 | 4.936 |
| fr-melisma | fr | 4 | 2.403271 | 0.6296 | 5.987 |
| en-regression | en | 3 | 1.811167 | 0.6242 | 6.055 |
| vocalise-default | vocalise | 3 | 1.811167 | 0.5838 | 6.430 |

Tempo totale effettivo delle otto prove: **46,538 s**. WAV, richieste, log, audit e attribuzioni AI/Qixuan/DiffSinger sono in `validation/qixuan-itfr-final-audio/`. Il modello può produrre campioni differenti fra esecuzioni: gli hash descrivono questi file precisi, non una promessa di determinismo.

Test mirati: **82 passed, 3 skipped, 1 warning**, 4,68 s; i tre skip sono test G2P facoltativi nell'ambiente generale, mentre le 78 parole e le otto inferenze reali sono state eseguite nel runtime Qixuan isolato. **Non sommare** questo conteggio alla regressione generale che comprende gli stessi test. Ruff, compilazione Python e sintassi JavaScript superati.

### Uso e collaudo

1. Importare il nuovo bundle completo dal gestore asset, mantenendo i controlli sulle singole licenze e l'attivazione dell'operatore; non eliminare automaticamente la banca precedente.
2. Selezionare la nuova banca in Vocal Studio, lingua IT oppure FR, e inserire sillabe o testo completo. Il pannello segnala la proiezione. Per il testo completo la pronuncia usa il profilo automatico e l'eventuale sequenza esplicita di conteggi per melisma.
3. Per riprodurre queste prove con un runtime già installato e autorizzato, usare `validation/r210-qixuan-itfr-real.py --bundle-root <cartella estratta> --manifest-sha256 <SHA manifest effettivo> --output <nuova cartella>`. Il comando non scarica modelli e non attiva policy.
4. Ascoltare pronuncia, accento, timbro, transizioni e melismi, in particolare rotiche, palatali, nasali e arrotondate. Questi restano collaudi d'ascolto. La banca originale non diventa nativamente italiana/francese grazie al mapping e non viene dichiarata tale.

## English

Separate pinned EN/IT/FR profiles, per-language selection, explicit phone editing, native-prefix validation, default X-SAMPA vocalise mapping, bounded literal/glide rules, UI disclosure and singer-specific pronunciation receipts are implemented. Qixuan's original acoustic languages are English/Japanese/Mandarin; **IT/FR are explicit cross-language projections**, with disclosed rhotic/palatal/nasal/rounded-vowel approximations. No unsupported language ID, model training or native-pronunciation certificate is invented.

Actual eSpeak processed **78 IT/FR words** without unmapped phones. The exact final complete bundle ran **eight real CPU acoustic/vocoder ONNX bridge cases** at 32 steps: Italian text/palatals/melisma, French text/nasal-rounded/melisma, English regression and the UI's default vocalise. All outputs were finite, non-silent mono 48 kHz PCM24 and score duration agreed within 25 ms. Total wall time was 46.538 s. Requests, actual IPA/phones, logs, WAV hashes and attribution are retained. Tests use explicit synthetic contracts separately and are not mislabeled neural evidence.

The final 474,464,355-byte bundle passed full ZIP CRC and every file inventory check. All 37 original bank/vocoder members are byte-identical; final engine source evidence matches. The new asset remains disabled pending genuine operator review. No model weights, licensing policy, commercial-service approval, legacy AI, VST SDK, Git or production server was modified. Listening and native-quality limitations are explicit, rather than hidden behind a successful runtime test.
