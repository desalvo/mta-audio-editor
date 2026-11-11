# MTA 0.3.0-r210 — basso e separazione delle voci

Aggiornato: 11 novembre 2026. Questo documento distingue integrazione software,
diritti dei checkpoint e validazione musicale. Nessun ascolto reale è approvato
automaticamente dall’installazione.

## IT — Estrazione del basso opzionale

In **Separa strumenti**, sia per un nuovo brano sia dal menu della traccia,
sono disponibili due profili aggiuntivi:

* **BS RoFormer ZFTurbo · Bass + accompaniment**: produce basso e accompagnamento.
  Selezionare **Solo basso** per importare soltanto il basso. L’accompagnamento è
  la sottrazione in virgola mobile del basso dal mix di ingresso; i due file
  ricostruiscono l’ingresso senza normalizzazioni indipendenti.
* **BS RoFormer ZFTurbo · 4 stems**: drums, bass, other, vocals.

Demucs resta il predefinito. I due profili non sono BS RoFormer SW e non usano
pesi SW. Cardinalità incompatibili sono rifiutate senza sostituire il modello.
Su iOS la richiesta passa al server, senza usare un modello Core ML differente.

Sulla traccia esistente il nuovo percorso renderizza prima tagli, spostamenti,
gain di ingresso e insert. Il rendering è pre-fader: volume/pan/mute del mixer
non sono incorporati. Il checkbox dell’intervallo usa i limiti della selezione
timeline in millisecondi; gli stem vengono inseriti nella posizione iniziale
dell’intervallo. Le estrazioni per intervallo non sostituiscono precedenti stem
della traccia. La traccia originale rimane disponibile.

### Installazione, verifica, rimozione

1. Aprire **Amministrazione / impostazioni native → Modelli AI**.
2. Esaminare la scheda licenze del modello `bs-roformer-zfturbo`.
3. Nel gruppo separazione scegliere l’acceleratore del runtime BS RoFormer:
   Auto, CPU, CUDA o ROCm. Premere il tasto di installazione del runtime completo.
4. Il job con finestra di progresso installa il sorgente a commit fissato,
   dipendenze, configurazione e checkpoint. L’attivazione tecnica del runtime
   avviene solo dopo verifica degli hash, backend CPU/CUDA/ROCm, calcolo sul
   dispositivo e caricamento rigoroso dei quattro stem con trasferimento sul
   dispositivo scelto. Dettagli e limiti: [verifica dispositivo](BS_ROFORMER_DEVICE_VALIDATION_R210_IT_EN.md).
5. Completare la revisione documentata dei diritti prima dell’inferenza. Il
   download non attiva la policy: il modello è disabilitato per default, anche
   in un servizio non commerciale. Il controllo si applica anche al worker.

Runtime e checkpoint hanno tasti di rimozione separati con finestra di progresso.
La rimozione del checkpoint conserva il runtime; nessun download avviene durante
la separazione. In presenza di worker remoto l’installazione va fatta sul nodo
che esegue il modello, non soltanto sul server web. Sono necessari Git, FFmpeg,
un Python di base del runtime AI e accesso alle fonti ufficiali.

### Identità e licenze separate

| Elemento | Identità / condizioni |
|---|---|
| Codice MSST | Commit `ea7eb9c20ea0e3f94368a30fc1654b51cdd55789`, MIT |
| Checkpoint | Release v1.0.12, `model_bs_roformer_ep_17_sdr_9.6568.ckpt`, 527385512 byte |
| SHA-256 pesi | `3e9daecd70aaed5b5a0d1f861cc4d77eaa45afb3fc6301b1cf32c1be0f5868fb` |
| YAML | `config_bs_roformer_384_8_2_485100.yaml`, 4566 byte |
| SHA-256 YAML | `d8afb980318d0c08b9c2e24a7adc00d4f3150320c127a7e4de861800d1321939` |
| Licenza checkpoint | MIT dichiarata dall’autore per questo file; attribuzione a ZFTurbo |
| Dati di training | MUSDB18-HQ; l’autore lascia la valutazione delle relative condizioni al distributore/operatore |

Fonti: [release ufficiale](https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/tag/v1.0.12),
[conferma dell’autore sui pesi](https://github.com/ZFTurbo/Music-Source-Separation-Training/issues/254#issuecomment-5914058767),
[dataset](https://sigsep.github.io/datasets/musdb.html).
In questo sviluppo sono stati controllati dimensione e SHA-256 di YAML e pesi
scaricati dalla release. Non è stata eseguita inferenza con il modello neurale
reale. I test sintetici dimostrano il protocollo, il DSP e la pubblicazione,
non un miglioramento sonoro rispetto a Demucs.

### Evidenze dei diritti e decisione di deployment — 11 novembre 2026

La release ufficiale identifica MUSDB18-HQ come dataset di addestramento. Nella
[risposta del 30 settembre 2026](https://github.com/ZFTurbo/Music-Source-Separation-Training/issues/254#issuecomment-5914058767)
ZFTurbo dichiara MIT per **questo checkpoint**, richiede il credito ZFTurbo e
lascia all'utilizzatore la verifica delle eventuali condizioni dei dati. La
[pagina ufficiale SigSep](https://sigsep.github.io/datasets/musdb.html) precisa
che il dataset contiene brani di provenienze diverse, alcuni con condizioni
non commerciali, e che l'accesso ai brani è per scopi accademici; identifica
MUSDB18-HQ come versione non compressa dello stesso dataset. Queste informazioni
riguardano il dataset: non stabiliscono da sole se o come le sue restrizioni si
applichino ai pesi addestrati o a uno specifico servizio. La risposta del
creatore dei pesi non risolve i diritti di terzi.

Per ogni deployment, documentare separatamente: identità e hash del checkpoint;
crediti e avvisi MIT; uso previsto (ricerca, servizio non commerciale o
commerciale, distribuzione di pesi/conversioni); base dei diritti dei dati e
relative fonti o parere competente; responsabile e data della decisione. Le
autorizzazioni relative ai brani caricati dagli utenti sono un tema distinto.
Fino a una decisione documentata per il caso specifico la policy rimane
disabilitata. Nessuna approvazione di deployment è stata ottenuta in questa
revisione, né viene dedotta automaticamente dal regime non commerciale.

### Confronto musicale prima di cambiare il predefinito

Eseguire entrambi i separatori sulla stessa sorgente e sullo stesso intervallo;
confrontare gli stem in solo a pari livello. Annotare cassa residua, note perse,
attacco, armoniche, artefatti, tempo e memoria. Per un intervallo molto breve
preferire un’estrazione più lunga da ritagliare dopo, per conservare contesto.
Il checkpoint pubblico a quattro stem non eredita i punteggi dei modelli bass
specializzati MVSep o della variante SW.

## IT — Candidati cori, duetti e sovraincisioni (ricerca; non aggiunti)

| Caso | Candidato | Stato dei diritti / limite |
|---|---|---|
| Voce principale e cori | MVSep Karaoke BS RoFormer 124 bands; MelBand RoFormer Karaoke / fused | Benchmark lead/back disponibili; ogni checkpoint richiede fonte, hash e licenza originale. Il servizio non concede automaticamente redistribuzione dei pesi. |
| Duetto, due linee vocali | BS/Mel RoFormer Duet di Play da Segunda/viperx | Candidati specializzati valutati su MedleyVox; licenza dei checkpoint da confermare. |
| Duetti e unisoni | `Cyru5/MedleyVox` | Model card dichiara CC BY 4.0. Provenienza esatta, dipendenze, file e dati di training vanno ancora verificati. Non confondere con la licenza del dataset MedleyVox. |
| Voci molto correlate / armonizzazioni | UNMIXX | Ricerca ICASSP 2026 specifica per voci correlate. Repository e checkpoint richiedono revisione puntuale; nessuna integrazione approvata. |
| Duetto uomo/donna | MVSep Male/Female | Può beneficiare di voci già isolate. Non è una soluzione generale per due parti cantate dalla stessa persona. |

Fonti primarie:
[MVSep Karaoke](https://mvsep.com/algorithms/76?lang=en),
[Duet BS](https://mvsep.com/quality_checker/entry/7904),
[Duet Mel](https://mvsep.com/quality_checker/entry/7927),
[Cyru5 checkpoint](https://huggingface.co/Cyru5/MedleyVox),
[MedleyVox dataset](https://zenodo.org/records/7984549),
[UNMIXX](https://github.com/jihoojung0106/unmixx),
[Male/Female](https://mvsep.com/en/tools/male-female-vocal-separation).

Il nome `mel-band-roformer-deux` non indica separazione di un duetto: la sua model
card descrive voce/strumentale ed espone CC BY-NC 4.0. Per cori della stessa
persona, l’ipotesi da provare è isolare prima tutte le voci e poi separare lead e
armonie con un modello specifico. Parti all’unisono, con uguale timbro e posizione
stereo, possono essere non separabili in modo univoco dal mix: non si promette
il recupero delle singole registrazioni originali.

## EN — Optional bass separation

The instrument separation dialogs expose **BS RoFormer ZFTurbo · Bass +
accompaniment** and **BS RoFormer ZFTurbo · 4 stems**. Demucs remains the default.
Select **Bass only** to import a single bass output. Accompaniment is computed
by floating-point subtraction from the actual input, retaining the residual.
This integration supports only the original v1.0.12 checkpoint identified above,
not SW weights. Mismatched stem counts fail without model substitution.

Existing-track separation renders timeline edits, input gain and inserts before
an optional selected interval. This is pre-fader audio. Interval stems retain
their start position and do not replace earlier outputs. Mobile requests use
the server rather than a different local Core ML model.

Under administrator/native **AI Models**, choose the BS RoFormer accelerator
and explicitly install the complete runtime. Progress covers source acquisition,
dependencies, YAML, checkpoint, device computation and strict state loading
with model transfer to the selected CPU/CUDA/ROCm device. See
[device validation](BS_ROFORMER_DEVICE_VALIDATION_R210_IT_EN.md) for scope and limits.
Runtime and checkpoint
can be removed independently. Install on the actual execution node; installing
the web host does not configure a remote worker. No inference-time download or
fallback occurs. Downloading and successful loading do not grant deployment
rights or prove neural audio quality.

The code and this exact checkpoint have separate MIT evidence. The author
specifically leaves MUSDB18-HQ training-data conditions for deployment review.
The checkpoint policy remains disabled until documented operator review.
Non-commercial operation does not itself settle missing rights. Preserve
ZFTurbo credit and the applicable notices. The exact official configuration and
checkpoint hashes were verified during development; real neural inference and
listening acceptance remain pending.

On 11 November 2026 the official dataset description was reviewed alongside the
author's checkpoint-specific statement. SigSep describes multiple data sources,
some with non-commercial conditions, and academic access to the recordings;
MUSDB18-HQ is the uncompressed version. Whether and how these data terms apply to
trained weights or a particular deployment remains an open question, not an
automatic prohibition or permission. Record the exact checkpoint/hash, MIT
notices, intended deployment and distribution, training-data rights evidence,
decision maker and date. User-provided music rights require separate review.
The model policy remains disabled pending a documented decision for the use.

## EN — Vocal candidates

Karaoke lead/backing models target musical role; dedicated Duet models target
two vocal lines; male/female models target different voice categories. These
tasks are not equivalent. Cyru5/MedleyVox declares CC BY 4.0 for its model card,
with provenance and training details still to audit. UNMIXX specifically targets
highly correlated singing mixtures, but requires a separate code/checkpoint
license review before integration. None of these new vocal candidates is
installed or enabled by this bass implementation. Same-singer harmonies should
be tested separately from doubled unison; perfect recovery is not guaranteed.
