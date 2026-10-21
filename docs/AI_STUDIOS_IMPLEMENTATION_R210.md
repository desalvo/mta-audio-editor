> Stato aggiornato / Current status: vedere [correttezza dei risultati combinati](R210_COMBINED_RESULTS_IT_EN.md), [runtime reali](R210_DIFFSINGER_DEEP_CLOSURE_IT_EN.md) e [guida ai collaudi](R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md). Le sezioni di avanzamento qui sotto documentano una fase precedente e non rappresentano il catalogo attuale. Earlier progress sections below are historical, not the current model catalog.

Aggiornamento corrente: [STUDIO_WORKFLOWS_R210.md](STUDIO_WORKFLOWS_R210.md). Le sezioni seguenti descrivono il checkpoint delle fondamenta precedente; sono ora aggiunti UI di progetto, installazione modello, workflow in coda e corsie controller. Le specifiche AI integrali restano incomplete.

# AI Vocal Studio / Multi-Track Audio-to-MIDI — checkpoint r210

Versione: **0.3.0-r210**. Questo checkpoint non è la consegna completa dei due moduli.
Le specifiche funzionali ricevute il 20 ottobre 2026 rimangono i criteri di accettazione.

## Stato delle macroaree

| Area | Stato | Risultato effettivo / limite |
|---|---|---|
| Interoperabilità musicale | Implementata, verificata localmente | Protocollo `mta-music-1`: parti indipendenti, note/controller, offset, provenienza, alternative. Nessuna parte vuota/fittizia. Budget aggregato di eventi. |
| Importazione nel progetto | Implementata, verificata localmente | Endpoint autorizzato `POST /api/projects/{pid}/midi/music`; pubblicazione atomica, revisione attesa, replay senza duplicati, nomi univoci, alternative persistenti, media conservati dopo errori successivi al commit. |
| Armonizzazione MIDI | In sviluppo | Motore indipendente dal modello, 2–8 voci, estensioni, nessun incrocio, penalità per salti e parallele, priorità agli accordi confermati. Prove a 4 e 8 voci. Nessuna valutazione percettiva completata; stili pop/rock/gospel non abilitati. |
| Sintesi vocale | Bloccata per la produzione | Nessun voicebank autorizzato e validato incluso. DiffSinger/Amphion/RVC/Seed-VC da valutare separatamente per codice/pesi/lingua/voicebank. Nessun audio sostitutivo presentato come canto sintetico. |
| Lyrics/fonemi/Singers/Expression/preset | Non iniziata | Mancano allineamento sillabe-note, melismi, fonemi IT/EN/FR e UI Vocal Studio. |
| Trascrizione di sorgente isolata | Implementata, verifica locale CPU | Adapter Basic Pitch 0.4.0 ONNX reale; nessun download durante l’inferenza. SHA modello verificato; risultato JSON modificabile. Prova tramite la coda e il ledger esistenti. Non è un classificatore multistrumento. |
| Trascrizione multistrumento | Non iniziata | YourMT3+/MT3/MR-MT3/Transkun/MT3-Infer non abilitati. Mancano riconciliazione multimodello, specializzazione per strumento, UI conflitti e valutazione su mix reali. |
| Capacità 10/16 parti | Verificata nel formato/editor/import, non nell’inferenza | Test reale di pubblicazione di 16 parti MIDI distinte; nessuna garanzia che Basic Pitch riconosca 16 strumenti. |
| Job AI | Parzialmente verificata | Basic Pitch passa dal protocollo worker e dalla coda globale con CPU registrata. Mancano workflow UI dedicato, checkpoint/ripresa fasi, cache e test completi di cancellazione/retry dei nuovi moduli. |
| SMF2 e SMPTE | Implementata, verificata localmente | Pattern con mappe tempo indipendenti; SMPTE 24/25/29.97/30. SMF0/1 conservano i tempi in ms con griglia progetto; verificare/rimappare canali prima di unire pattern indipendenti che condividono canali. |
| Editor MIDI | In sviluppo, funzioni implementate verificate | Piano roll virtualizzato, selezione multipla, spostamento/resize, trasformazioni, undo/redo, lista eventi ricercabile/paginata, metadati. Non dichiarato editor professionale completo: controller lane/automazioni grafiche e operazioni avanzate restano da completare. |
| Strumento GM | Implementata, prove reali locali | FluidSynth + FluidR3 GM: audio reale offline e nel worker server. Parametri per traccia, programma/banco/gain/polifonia/reverb. Dipendenze/banco non inclusi automaticamente nel package sorgente. |
| Metronomo MIDI/grafico | Implementata, verificata localmente in parte | MIDI collegato alla griglia fissa/zone/adattiva; cambia con marker/BPM. Grafico BPM in finestra o overlay; tempo adattivo di sola lettura. Prove di editing grafico estese ancora necessarie. |
| Preferenze DB | In sviluppo | Preferenze dell’editor/sidebar/dispositivi MIDI persistite per identità tramite patch lazy, coda durevole nel browser e retry. Non tutte le impostazioni native storiche sono già migrate dal file locale al DB. |
| ASIO e matrice audio/MIDI completa | Non iniziata in questo checkpoint | Rimane il routing preesistente. Nessuna certificazione su driver/interfacce fisiche Windows/macOS. |
| ROCm/CUDA nuovi adapter | Non verificata | Basic Pitch usa esclusivamente ONNX CPU. Nessuna fatturazione GPU prodotta o inventata. |
| Accettazione dei due moduli | Bloccata / incompleta | Non soddisfatte tutte le condizioni di consegna 1–10 delle specifiche. |

## Utilizzo delle funzioni già disponibili

Aprire la sezione **MIDI** della sidebar (collassata per default). Creare/importare una traccia, modificarne le note nel piano roll o nella lista eventi e salvare prima di chiudere l’editor. Le trasformazioni agiscono sulle note selezionate e sono annullabili; la quantizzazione non riscrive l’audio originale. Il metronomo MIDI rimane derivato dalla griglia: disabilitare il collegamento prima di modificare manualmente le sue note.

L’esportazione multitraccia permette SMF0, SMF1 e SMF2, PPQ o SMPTE. I metadati MIDI importati restano nel progetto. Gli eventi UMP richiedono l’esportazione JSON senza perdita, non una conversione SMF implicita.

Lo strumento General MIDI richiede una libreria FluidSynth dinamica e il banco **FluidR3 GM 3.1** esatto, SHA-256:

`74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0`

Percorsi riconosciuti: `soundfonts/FluidR3_GM.sf2` nella directory dati dell’app, `/usr/share/sounds/sf2/FluidR3_GM.sf2` e `/usr/share/soundfonts/FluidR3_GM.sf2`. L’amministratore può impostare `MTA_GM_SOUNDFONT_DIR` e `MTA_FLUIDSYNTH_LIBRARY`; non sono percorsi accettati dai client. Il banco ha dimensione 148.398.306 byte. I progetti MIDI restano apribili/editabili anche quando il sintetizzatore non è disponibile. L’installazione guidata del banco su tutte le piattaforme resta da integrare.

## Adapter Basic Pitch sperimentale

Non aggiunto all’installazione automatica né abilitato in produzione: l’ambiente deve essere scelto esplicitamente dall’operatore dopo la revisione delle licenze/dipendenze. Non installare nello stesso venv del server/ROCm: richiede NumPy 1.26 e dipendenze diverse dal runtime principale.

Ambiente locale effettivamente provato: Python 3.12, Basic Pitch 0.4.0, ONNX Runtime 1.31.0, NumPy 1.26.4, librosa 0.11.0, resampy 0.4.2, pretty-midi 0.2.11.post0, pydantic 2.12.5, setuptools 80.10.2. TensorFlow non necessario per l’adapter ONNX. `basic-pitch` va installato con `--no-deps`, quindi con le dipendenze ONNX esplicite; i metadati upstream continuano a richiedere TensorFlow e un `pip check` generale segnalerà quella differenza intenzionale. Questo non equivale a un lockfile produttivo completo.

Registrazione nell’**esistente** file operatore `MTA_AI_ENGINE_REGISTRY_FILE` (aggiungere senza sovrascrivere altre voci):

```json
{
  "kind": "audio-to-midi",
  "executable": "/usr/lib/mta-audio-editor-server/app/ai_studio_adapter.py",
  "python": "/opt/mta/studio-basic-pitch/bin/python",
  "gpu_capable": false,
  "label": "Basic Pitch ONNX — isolated source pilot"
}
```

La radice del file registro è una lista. Percorsi assoluti da adattare all’installazione reale; adapter eseguibile, selezionato solo dall’operatore. Richiede `MTA_AI_WORKER_ENABLED=true`. L’API token preesistente `POST /api/ai-jobs/execute-audio/audio-to-midi` riceve WAV e opzioni nel formato già usato dagli altri adapter. Piano consentito: `{"options":{"onset_threshold":0.5,"frame_threshold":0.3,"minimum_note_length":127.7,"name":"Part","program":0}}`. `program` è un’indicazione esplicita dell’utente, non una classificazione del modello.

Input del pilot: mono/stereo, massimo 10 minuti e 192 kHz; il trasporto AI esistente può imporre frequenze/formati WAV più restrittivi. Nessun caricamento di codice o checkpoint dal client; modello ONNX incluso nel pacchetto upstream con SHA-256:

`2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`

Output `music.json` nel manifest artefatti esistente. Velocity derivata dall’attivazione del modello; **non** probabilità di correttezza. Pitch bend non importato dal pilot. Nessun BPM progetto sovrascritto. Progress per fasi senza percentuali durante l’inferenza, perché upstream non espone un totale affidabile.

`midi/music` richiede `publication_id` (32 caratteri esadecimali), `expected_revision` ottenuta da `GET /api/projects/{pid}/midi/revision`, e `result` conforme a `mta-music-1`. La revisione viene verificata sotto lock. Un replay identico non aggiunge tracce; un risultato diverso con lo stesso ID è rifiutato. Un progetto modificato richiede revisione esplicita dell’utente prima di una nuova importazione. Nessuna metrica/billing dal payload musicale viene trattata come attendibile.

## Licenze e limiti di distribuzione

| Componente | Fonte primaria / licenza | Esito del checkpoint |
|---|---|---|
| FluidSynth | https://github.com/FluidSynth/fluidsynth/blob/master/LICENSE — LGPL-2.1 | Integrazione dinamica; conservare avvisi e obblighi della versione distribuita. Nessun binario terzo incluso in questo sorgente. |
| FluidR3 GM | https://sources.debian.org/src/fluid-soundfont/3.1-6/debian/copyright — banco MIT | Distinguere dal packaging Debian `debian/*` GPL-2+. Banco scaricato solo nell’ambiente di prova, non incluso nello ZIP. |
| Basic Pitch | https://github.com/spotify/basic-pitch/blob/main/LICENSE — Apache-2.0 | Modello ONNX incluso nel wheel provato, checksum verificato. Non ridistribuito nello ZIP. Revisione completa delle dipendenze/dati per distribuzione produttiva pendente. |
| YourMT3+ | https://github.com/mimbres/YourMT3 | Codice GPL-3; pesi/dataset e obblighi del prodotto da verificare. Non abilitato. |
| MT3-Infer | https://github.com/openmirlab/mt3-infer | Verifica separata delle componenti vendorizzate e dei pesi necessaria. Non incluso/abilitato. |
| DiffSinger/Amphion/RVC/Seed-VC | Repository ufficiali dei singoli progetti | Nessun voicebank autorizzato incluso; licenze codice/pesi/dataset/voicebank e supporto IT/EN/FR da verificare. |

La separazione in processi non è una conclusione automatica di compatibilità delle licenze. Nessuna voce riconoscibile di terzi è inclusa. Nessuna compatibilità ROCm/CUDA dei nuovi modelli viene dichiarata dal solo import Python.

## Checkpoint di ripresa

1. Terminare catalogo modelli/installazione/self-test con evidenze hardware e licenze separate.
2. Collegare UI Source/Execution/Results al pilot e alla pubblicazione musicale, con cancellazione/retry/recovery end-to-end.
3. Integrare un modello multistrumento con pesi autorizzati e valutare dataset comparabili; solo dopo abilitare modalità accurate/massima.
4. Integrare sintesi/conversione vocale con voicebank autorizzati, fonemizzazione IT/EN/FR e allineamento lyrics, poi rendering delle armonizzazioni.
5. Completare ASIO/routing multicanale, editor CC/automazioni, test hardware e metronomo grafico.
6. Eseguire le accettazioni complete delle specifiche prima di chiamare completi i due moduli.
