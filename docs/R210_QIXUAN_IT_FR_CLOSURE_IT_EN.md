# Qixuan IT/FR — chiusura software e prove reali / Software closure and actual tests

21 ottobre 2026 · MTA Audio Editor **0.3.0-r210**, invariata.

## Italiano

L'implementazione IT/FR per la banca Qixuan esistente è completata: profili fissati, selezione per lingua, fonemi espliciti, vocalizzi, testo/sillabe e melismi, receipt e avvisi. La banca contiene modelli acustici EN/JA/ZH: **IT/FR sono proiezioni dichiarate**, non un nuovo addestramento nativo. Pronuncia e resa artistica richiedono l'ascolto dell'utente, in particolare vibranti, palatali, vocali nasali e arrotondate.

### Difetti effettivamente corretti in questo ciclo

1. **Dipendenze separate tra Studio e runner:** il processo principale poteva non avere eSpeak anche quando il runtime Qixuan era completo. Ora, quando la dipendenza locale è assente, la fonemizzazione viene eseguita dallo stesso **interprete DiffSinger fissato con SHA-256**, tramite un helper offline. Non servono una seconda copia di eSpeak o variabili manuali verso librerie dell'altro venv. Se è stata configurata esplicitamente una libreria locale difettosa, l'errore resta visibile: non viene ignorata. Interprete e profilo sono verificati, JSON e tempi di esecuzione sono limitati, note/pitch/timing/velocity devono essere conservati. Non vengono accettati comandi o interpreti dal client.
2. **Liaison francese persa nel testo completo:** la precedente fonemizzazione parola per parola perdeva il contesto. I profili Qixuan IT/FR usano ora l'intera frase e verificano la corrispondenza esatta dei confini di parola. `les amis`, `un ami` e `vous avez` conservano le consonanti contestuali; `les haricots` conserva l'assenza di liaison indicata da eSpeak. Il trattino di annotazione eSpeak viene rimosso con una riscrittura letterale esplicita nel profilo francese, non con un fallback per fonemi sconosciuti. Allineamenti ambigui vengono rifiutati e possono essere revisionati tramite fonemi espliciti.
3. **Readiness incompleta:** `scripts/check_diffsinger_ready.py` esercita davvero G2P e inventario per ogni profilo EN/IT/FR, segnalando anche un runtime fonetico incompleto. Il controllo continua a distinguere readiness da inferenza acustica e dalle genuine autorizzazioni dei modelli.
4. Il builder accetta anche l'esatto precedente bundle v2 verificato e produce un **ID distinto**, così la nuova banca può coesistere con quella precedente senza eliminarla o sovrascriverla.

### Pacchetto completo

`MTA-Qixuan-2.7.0-IT-EN-FR-context-r210-final-bundle.zip` · **474,466,435 byte**.

SHA-256: `9ddc578cc4df3997d9a6725cdfeef6966ff51eeb9ca657d42ec78d22c85ee64f`.

ID: `qixuan-2-7-onnx-it-en-fr-context-r210`. CRC ZIP completo, tutti gli SHA/dimensioni, conservazione di tutti i membri precedenti e confronto byte per byte dei **37 membri originali** banca/vocoder superati. Le evidenze del motore corrispondono ai sorgenti finali. Nessun peso viene modificato; termini e avvisi originali sono inclusi. Il pacchetto resta disabilitato fino alla vera revisione/attivazione dell'operatore; importazione e prove non concedono diritti commerciali.

### Prove effettive

- **78 parole IT/FR** nuovamente fonemizzate realmente con eSpeak, senza fonemi sconosciuti.
- **12/12 vere inferenze CPU ONNX**, acustico e vocoder originali, 32 passi. Il processo principale usa il venv generale **senza espeakng-loader**, passa dal nuovo helper nell'interprete Qixuan isolato e produce gli audio tramite il bridge MTA. Non si usa una fixture come sostituto di alcuna inferenza.
- Tutti gli output sono finiti e non silenziosi, mono **48 kHz PCM24**, con durata entro **25 ms** dalla partitura. Totale wall time delle inferenze: **426.458 s** nell'ambiente disponibile; il valore include l'avvio del runner e dipende dall'ambiente. Non è un benchmark prestazionale universale.
- Probe G2P di readiness effettivi per **EN/IT/FR** riusciti. Questi probe non sono ulteriori inferenze acustiche.
- Contratti automatici: **74 passed, 3 skipped**. I tre skip riguardano le prove G2P locali facoltative nel venv generale; le esecuzioni reali separate coprono il runtime autorizzato. I conteggi mirati si sovrappongono alla regressione generale e non si sommano. Ruff e compilazione Python superati; `pip check` del runtime Qixuan pulito.

| Caso | Lingua | Note | Durata WAV (s) | Picco | Wall (s) |
|---|---|---:|---:|---:|---:|
| it-text | it | 4 | 2.403271 | 0.6621 | 81.407 |
| it-palatals | it | 3 | 1.811167 | 0.5429 | 24.901 |
| it-melisma | it | 5 | 3.007000 | 0.6601 | 32.205 |
| fr-text | fr | 3 | 1.811167 | 0.5631 | 24.465 |
| fr-nasal-rounded | fr | 3 | 1.811167 | 0.5064 | 14.917 |
| fr-melisma | fr | 4 | 2.403271 | 0.5901 | 59.199 |
| fr-liaison-les-amis | fr | 3 | 1.811167 | 0.5591 | 46.638 |
| fr-no-liaison-aspirated-h | fr | 4 | 2.403271 | 0.5146 | 21.853 |
| fr-liaison-un-ami | fr | 3 | 1.811167 | 0.5892 | 21.552 |
| fr-liaison-vous-avez | fr | 3 | 1.811167 | 0.5535 | 58.778 |
| en-regression | en | 3 | 1.811167 | 0.5671 | 22.732 |
| vocalise-default | vocalise | 3 | 1.811167 | 0.5978 | 17.811 |

Audio, richieste, log, audit e attribuzioni: `validation/qixuan-itfr-context-final-audio/`. Le prime otto prove riprendono il precedente corpus, aggiungendo quattro casi contestuali francesi. Gli hash identificano queste esecuzioni precise; non viene promessa identità bit per bit tra generazioni.

### Installazione e collaudo

Importare il nuovo ZIP completo da **Impostazioni → Modelli AI**, conservare/revisionare le condizioni delle componenti e abilitare soltanto con i diritti effettivi. Selezionare la nuova banca e lingua IT/FR in Vocal Studio. Il runtime esterno deve avere `requirements-studio-diffsinger-onnx.txt` (che include `espeakng-loader==0.2.4`), un interprete regolare con SHA fissato in `MTA_DIFFSINGER_PYTHON` / `MTA_DIFFSINGER_PYTHON_SHA256`, e il normale worker Studio configurato. Nelle app congelate il worker deve essere un Python esterno reale secondo la configurazione esistente, non l'eseguibile GUI.

Non è più obbligatorio installare eSpeak anche nel processo principale: il nuovo helper riusa il runtime verificato quando manca la dipendenza locale. Le configurazioni locali già funzionanti restano supportate. Per riprodurre il percorso verificato usare `validation/r210-qixuan-completion-real.py --bundle-root <estratto> --manifest-sha256 <SHA reale> --runtime-python <Python fissato> --output <nuova cartella>`, dal Python Studio senza eSpeak.

Le prove di questo ciclo sono effettive su Linux CPU. Le chiamate usano percorsi/interpreti indipendenti dalla piattaforma, ma non sostituiscono il collaudo dei pacchetti Windows/macOS, dispositivi o l'ascolto linguistico. Non restano implementazioni IT/FR mancanti per questo percorso della banca esistente; una pronuncia acustica nativamente addestrata richiederebbe un'altra banca/addestramento autorizzato, e non viene dichiarata ottenuta dal mapping. Nessuna policy, contabilità, versione, Git o macchina di produzione è modificata da queste prove.

## English

The IT/FR software path for the existing Qixuan bank is complete: pinned profiles, per-language selection, explicit phones, default vocalise, contextual full-text alignment, melismas, receipts/disclosures and deployment readiness. **Italian/French remain explicit projections onto the original EN/JA/ZH acoustic bank, not native trained languages.** Pronunciation/artistic listening remains required.

The parent/runner eSpeak dependency split is fixed: when local eSpeak is absent, G2P uses the same SHA-pinned DiffSinger interpreter through a bounded offline helper. Explicit broken local configuration fails visibly. Interpreter/profile hashes, phone inventory and unchanged musical data are checked. Full-text phonemization now preserves phrase context and French liaison; ambiguous word boundaries fail for manual review rather than guessed alignment. Readiness actually probes each lyric profile. The new distinct asset ID permits coexistence with the earlier complete bank.

The final 474,466,435-byte complete bundle passed full CRC, every file inventory check, final engine-source evidence and byte identity of all 37 original bank/vocoder members. All previous members and original licenses/notices are retained; no weights, rights or policy activation change. SHA-256: `9ddc578cc4df3997d9a6725cdfeef6966ff51eeb9ca657d42ec78d22c85ee64f`.

**Actual validation:** 78 real IT/FR G2P words and **12 CPU acoustic/vocoder ONNX cases at 32 steps**, driven from the main Studio environment without eSpeak through the verified external G2P runtime. All outputs are finite, non-silent mono 48 kHz PCM24 and match score duration within 25 ms. Total inference wall time: 426.458 s. Eight regression cases plus French `les amis`, `les haricots`, `un ami` and `vous avez` are retained with actual phones, WAV hashes, requests, logs and attribution. Three actual readiness G2P probes passed separately. Focused contracts: 74 passed / 3 optional local-G2P skips, overlapping the general suite. Ruff, compilation and runtime pip check passed. Linux CPU execution is proven; Windows/macOS package acceptance and linguistic listening remain distinct target checks.
