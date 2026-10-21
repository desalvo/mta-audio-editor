# r210 — GPU real-audio inference harness / Esecuzione GPU reale

## IT

Implementati: `scripts/run_mrmt3_resumable.py` ora accetta `--device cuda` (senza ripiego silenzioso su CPU), `--device auto` e `--min-free-gpu-gib`; `scripts/run_mrmt3_gpu_benchmark.py` orchestra riprese bounded con output durabile, offline e opt-in esplicito. Nessuna installazione/deploy automatico, nessun riavvio del servizio.

**Prerequisiti**: macchina Linux con CUDA disponibile, runtime MR-MT3 già installato in ambiente Python isolato, sorgenti MT3-Infer verificati, `model.safetensors` verificato, FFmpeg e audio di benchmark in un percorso privato. Usare preferibilmente un nodo GPU separato o una finestra di manutenzione; `--allow-production-gpu` autorizza solo il test, non la modifica del servizio.

Esempio (da radice repository, directory di lavoro privata):

```sh
python scripts/run_mrmt3_gpu_benchmark.py \
 --audio /path/to/All_Night_Long_rec1.MP3 \
 --model /path/to/model.safetensors \
 --output /path/to/private-mrmt3-results \
 --allow-production-gpu --min-free-gpu-gib 6 \
 --windows-per-cycle 4
```

Codice 2 = output incompleto riprendibile; codice 0 = inferenza completata, **non** qualità soddisfatta. Il file `prediction.json` rappresenta note grezze con provenienza; non è ancora un `MusicResult` certificato. Il confronto con il MIDI di riferimento richiede conversione/validazione indipendente e l'uso di `scripts/check_audio_midi_quality.py` sui due file MusicResult; per la valutazione rigorosa usare i criteri immutati presenti nel repository. Non inviare il MIDI originale all'inferenza o usarlo per correggere le predizioni. Evitare dati musicali privati nei log pubblici.

**Non verificato in questo ciclo**: GPU CUDA reale, prestazioni GPU, inferenza integrale Merish5, soglie qualitative 10–16 strumenti, regressione completa CI. Il runner GPU ha 13 test mirati (inclusi i test di ripresa CPU) superati senza una GPU; i test di guardrail non sono inferenze neurali.

## EN

Implemented explicit CUDA/CPU selection, free-GPU-memory gate, and opt-in offline restartable inference cycles. This does not connect to, deploy onto, or restart a production server. Python execution environment must contain the reviewed MR-MT3 source and dependencies, verified SafeTensors weights and ffmpeg. Run the sample command above from the project root in a dedicated private environment. Exit 2 denotes resumable incomplete inference; exit 0 denotes completed inference **not accuracy certification**. Ground-truth scoring, full-song inference, 10–16 instrument accuracy, and real CUDA validation remain open. Never train or condition predictions using the benchmark reference MIDI.


## IT — ROCm e installazione standalone / server condiviso (aggiornamento)

Il benchmark non richiede che il server MTA sia installato: necessita del repository estratto (per `scripts/`), di un venv dedicato e degli asset locali. Può essere eseguito su un nodo Linux indipendente o sulla macchina che ospita il server, senza usare il venv del servizio, senza riavvii e senza inviare l'audio ad alcuna API. `--backend rocm` impone PyTorch HIP AMD, `--backend cuda` impone NVIDIA CUDA, `--backend gpu` accetta entrambi ma rifiuta la CPU. Internamente PyTorch ROCm usa `torch.device('cuda')`: è il comportamento documentato da PyTorch. Non è una prova di compatibilità della specifica scheda AMD: verificare supporto GPU/ROCm/PyTorch e `torch.version.hip` prima della prova.

### Procedura (Linux, shell Bash; cartella dedicata)

1. Estrarre il cumulativo MTA in una directory dedicata (es. `$HOME/mta-benchmark`), senza sovrascrivere un'installazione produttiva. Portare sulla macchina `All Night Long_rec1.MP3`, `All Night Long.MID` e `model.safetensors` verificato, in una directory privata. Mettere i sorgenti estratti di MT3-Infer nella directory dedicata `external/mt3-infer`.
2. Creare un venv con versione Python supportata dalla build di PyTorch GPU scelta, es. `python3.11 -m venv .venv; source .venv/bin/activate; python -m pip install --upgrade pip`. Le versioni dei wheel PyTorch dipendono da OS, architettura GPU e ROCm/CUDA: selezionare il comando ufficiale sul sito PyTorch e NON installare il wheel CPU. Installare torch e torchaudio compatibili dal repository GPU ufficiale, poi il resto delle dipendenze di `requirements-studio-mrmt3.txt` **senza** reinstalla­re torch/torchaudio; usare `grep -Ev '^(torch|torchaudio)==' requirements-studio-mrmt3.txt > /tmp/mta-mrmt3-other-requirements.txt` e `python -m pip install -r /tmp/mta-mrmt3-other-requirements.txt`.
3. Installare il sorgente verificato MT3-Infer nel venv: `python -m pip install --no-deps -e external/mt3-infer`. Controllare `python -m pip check`, `ffmpeg -version`, `python -c 'import torch; print(torch.cuda.is_available(), torch.version.hip, torch.version.cuda, torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none")'`. Per AMD, HIP deve essere non nullo; per NVIDIA, CUDA deve essere non nullo.
4. Da root MTA, per AMD: `python scripts/run_mrmt3_gpu_benchmark.py --backend rocm --audio '/path/All Night Long_rec1.MP3' --model /path/model.safetensors --output /path/private-results --allow-production-gpu --min-free-gpu-gib 6 --windows-per-cycle 4`. Per NVIDIA sostituire `--backend cuda`. `--backend gpu` sceglie il backend rilevato. La flag `--allow-production-gpu` significa opt-in esplicito anche su host dedicato; non equivale a un'approvazione a occupare la GPU di altri utenti.
5. Il benchmark è riprendibile riutilizzando ESATTAMENTE output/audio/model/backend. Codice 0 significa inferenza completata, codice 2 incompleta ma riprendibile. Copiare `prediction.json` e gli output di audit all'esterno per la successiva valutazione quantitativa con MIDI reference separato. Non dichiarare raggiunta l'accuratezza dalla sola conclusione del runner.

**Server MTA condiviso:** usare utente di sistema non privilegiato, directory privata fuori dalle directory servite dal web, venv distinto da quello di `mta.service`, limiti di risorse e finestra concordata; verificare memoria GPU libera e lavori in corso. NON effettuare modifiche a systemd o deploy dell'app, né disabilitare la produzione. L'opt-in non riserva VRAM in maniera atomica; controllo memoria è preventivo, non isolamento garantito.

**Nota sulle versioni:** i pin `torch==2.8.0` e `torchaudio==2.8.0` nel file di requisiti erano concepiti per l'installazione CPU; sulla GPU scegliere wheel ROCm/CUDA ufficiali compatibili e non sovrascriverli. Se le versioni divergono, validare import, compatibilità delle librerie e inferenza breve prima dell'intero benchmark. Non usare comandi di installazione ROCm generici sulla produzione senza verifica hardware/driver.

## EN — ROCm and two deployment modes

A dedicated Linux machine does not need an installed MTA server. Alternatively, run on the same server host inside a private virtual environment, outside the production service, with explicit opt-in and VRAM safeguards. `--backend rocm` requires a HIP-enabled PyTorch build and AMD GPU; `--backend cuda` requires a CUDA-enabled build and NVIDIA GPU; `--backend gpu` accepts either but never falls back to CPU. PyTorch intentionally exposes HIP devices under the `cuda` device API. GPU performance and hardware compatibility are not certified here; an actual GPU run and reference-MIDI scoring are still required.
