**Aggiornamento PS/Deep:** variante PS originale installabile accanto a noPS, entrambe realmente eseguite; nuova [guida](R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md) e [risultati](R210_DIFFSINGER_DEEP_CLOSURE_IT_EN.md). Il default resta noPS. Target dieci strumenti non superato sullo stress test; classi vocali corrette e programmi GM proxy espliciti.

**Verifica aggiuntiva del 21 ottobre 2026:** installer completo ora eseguito dalla pubblicazione originale fissata, senza cache sorgenti precompilata; checksum, conversione safetensors e inferenza piano riusciti. Prova reale su dieci programmi GM: 5 parti e 7 note, target non superato. I precedenti riferimenti a 403 sono storici. Dettagli e limiti attuali: [report runtime](R210_REAL_RUNTIME_HANDOFF_IT_EN.md).

# YourMT3 e dispositivi audio — r210

Versione 0.3.0-r210 invariata. Questa integrazione non completa tutte le specifiche dei due Studio AI.

## Trascrizione multistrumento CPU

Il backend YourMT3 noPS usa la pubblicazione originale dell’autore nello Space [mimbres/YourMT3](https://huggingface.co/spaces/mimbres/YourMT3/tree/5e66c1ea173a8186e0d20432b841d3180cc015b5), commit `5e66c1ea173a8186e0d20432b841d3180cc015b5`. Il manifesto sorgenti riporta checksum e dimensione di ogni file. Nessun modello viene scaricato aprendo il progetto.

Ricetta di installazione esplicita Linux CPU (Windows/macOS non ancora supportati dalla ricetta), con Python 3.11/3.12, da una copia del progetto:

```sh
python3.12 scripts/install_studio_yourmt3.py \
  --runtime /opt/mta/studio-yourmt3 \
  --test-audio /percorso/campione-musicale-autorizzato.wav \
  --accept-apache-2-license
```

La ricetta crea un ambiente CPU separato, scarica soltanto file della revisione fissata, controlla hash/dimensioni, converte il checkpoint in safetensors ed esegue una vera inferenza prima di indicarlo come testato. Non modifica il runtime ACE-Step/ROCm. Il download del checkpoint è 561.544.628 byte; l’ambiente completo richiede ulteriore spazio per PyTorch e dipendenze. La ricetta è stata verificata con installazione Linux CPU pulita, sorgenti/pesi da cache locale verificata e dipendenze PyPI/PyTorch. Il primo download sorgenti è stato rifiutato dalla rete di questo ambiente (403): nessun runtime parziale è rimasto. È possibile usare `--source-cache /percorso/cache` con l’albero completo dei file fissati e del checkpoint, senza fallback di download dei sorgenti; ogni file viene comunque verificato. Runtime misurato: 1.810.689.063 byte. Job reale avviato anche dal browser sul nuovo runtime. Nessuna prova Rocky/Windows/macOS.

Eseguire la ricetta con l’account che esegue MTA, in una directory genitore scrivibile da tale account. Il runtime privato appartiene a quell’account; un’installazione root con permessi 700 non sarà leggibile da un servizio non root.

Applicare le tre variabili stampate dalla ricetta al servizio o all’app e riavviare:

```text
MTA_STUDIO_TRANSCRIBER=yourmt3
MTA_STUDIO_YOURMT3_RUNTIME=/opt/mta/studio-yourmt3
MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON=/opt/mta/studio-yourmt3/bin/python
```

Il modello selezionato vale per le trascrizioni servite da questa istanza. Audio-to-MIDI usa la coda globale e l’adapter già registrato, con contabilizzazione CPU, timeout/cancellazione del worker e import atomico nel progetto. Sono accettate regioni mono/stereo fino a dieci minuti; le parti rilevate sono raggruppate per programma GM, con percussioni separate. Nessuna parte viene aggiunta per raggiungere un numero prefissato. Rimuovere override manuali degli strumenti; le soglie Basic Pitch non si applicano.

Per tornare a Basic Pitch rimuovere `MTA_STUDIO_TRANSCRIBER` e l’override Python, mantenendo installato il runtime Basic Pitch. Fermare i job prima di cambiare modello o rimuovere un runtime. L’installer grafico, la disinstallazione e il selettore predefinito YourMT3 non sono ancora implementati; la gestione grafica Basic Pitch resta disponibile.

### Risultato verificato e limiti

Un WAV autorizzato sintetizzato localmente con FluidSynth/FluidR3 GM, quattro secondi, note pianoforte C4/E4/G4: tre note riconosciute con pitch e tempi corretti; programma pianoforte corretto. Verificati worker separato, coda MTA, circa 17 secondi CPU, importazione e rilettura della traccia MIDI salvata. È una prova tecnica di percorso, non un benchmark musicale generale.

Velocity 96 è **generata**, non rilevata. Nessuna confidenza calibrata, dinamica, CC, bend o articolazione viene inventata. Due esecutori dello stesso programma vengono aggregati. Non sono ancora verificati ROCm/CUDA, mix reali con dieci strumenti, modalità accurata/multimodello, riconciliazione e revisione delle alternative. Il modello ha tredici canali di decoding: questo non garantisce tredici strumenti riconosciuti in ogni registrazione.

## Licenze e provenienza

| Componente | Provenienza e condizioni |
|---|---|
| Sorgenti e checkpoint noPS | Space dell’autore originale, metadati Apache-2.0; revisione fissata sopra. Codice e pesi provengono dalla stessa pubblicazione, non da un mirror. |
| Checkpoint originale | SHA-256 `ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25`. Non redistribuito nello ZIP. |
| Conversione checkpoint | `weights_only=True`, hash originale obbligatorio, metadati personalizzati sostituiti da classi inerti, solo 655 tensori / 47.081.642 elementi. Nessun caricamento pickle durante l’inferenza. |
| Compatibilità T5 | Solo classi matematiche da Transformers v4.45.1, Apache-2.0, avviso conservato in `app/studio_assets/yourmt3_t5_compat.py`. Non include vecchio codice di download/deserializzazione; runtime Transformers 4.57.6. |
| Dipendenze | PyTorch BSD-style; torchaudio BSD-2-Clause; NumPy BSD-3-Clause; Transformers/Lightning/W&B Apache-2.0; librosa ISC; einops MIT; safetensors Apache-2.0; mido MIT; mir_eval MIT; smart-open MIT; soundfile BSD-3-Clause con libsndfile LGPL. Le dipendenze transitive/binarie vanno ricontrollate per la piattaforma di distribuzione. |
| Dataset | Nessun dataset o audio di addestramento viene distribuito. La pubblicazione del modello non costituisce una garanzia sui diritti di qualsiasi input dell’utente. |

Il file `app/studio_assets/Apache-2.0.txt` conserva il testo della licenza. Le modifiche MTA sono dichiarate: loader solo safetensors e import delle classi matematiche compatibili. Telemetria Hugging Face/Transformers/W&B disattivata; inferenza offline, nessun download automatico di altri modelli.

## Dispositivi audio nativi

Impostazioni → Audio devices / ASIO / routing permette di scegliere backend PortAudio, host API, dispositivi, buffer e matrici. La matrice di uscita collega il master stereo fino a 64 uscite fisiche; quella di ingresso collega fino a 64 ingressi a una registrazione stereo. Non equivale ancora a bus hardware indipendenti per ogni traccia. Preferenze nel database locale, driver mancante segnalato senza sostituirlo silenziosamente.

Il callback hardware è C++, senza callback Python, allocazioni o lock. Registrazione e riproduzione possono condividere uno stream duplex; overflow/disconnessioni producono errore esplicito. Provati callback compilati, matrici e stream PortAudio su ALSA virtuale. Nessun dispositivo fisico o driver ASIO Windows è stato certificato.

ASIO SDK ha condizioni proprie, distinte da VST3 MIT. La DLL ASIO del wheel sounddevice non viene inclusa automaticamente nei pacchetti: manca ancora il bundle verificato di sorgenti corrispondenti e avvisi. PortAudio standard resta incluso; build ASIO installate dall’operatore possono essere rilevate dal loader sounddevice. L’assenza di ASIO non deve impedire l’avvio dell’app.

## Workflow remoti

Le app native possono indirizzare Audio-to-MIDI e armonie MIDI al server configurato usando lo stesso token degli altri motori AI. Il server esegue il modello selezionato. Il journal conserva l’identità della richiesta: dopo un’interruzione recupera lo stesso risultato attestato, senza doppia esecuzione/addebito. I consumi server vengono mostrati localmente senza creare un secondo ledger locale. Le armonie usano una partitura JSON limitata e validata, non percorsi locali inviati al server.
