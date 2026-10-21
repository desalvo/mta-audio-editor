# YourMT3+ verified ROCm benchmark (IT/EN) — 0.3.0-r210

## IT — Procedura su Rocky Linux 10.2 / Radeon 8060S / ROCm 7.2.4 / Python 3.12

**Questo è un percorso di installazione e benchmark, non una certificazione dell'accuratezza.** YourMT3+ non è stato ancora eseguito sulla GPU reale con checkpoint verificato. MR-MT3 rimane la baseline indipendente (F1 rigoroso 9,49%). La sorgente deve essere il repository/Space pinned originale e il checkpoint deve superare il controllo byte-per-byte; NON scaricare pesi da fonti non verificate.

1. Estrarre questo archivio in una directory separata (non sovrascrivere l'installazione MTA in produzione). Attivare l'ambiente Python ROCm già verificato:

```
cd /root/mta-benchmark/mta-source
source /root/mta-benchmark/.venv/bin/activate
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
python -m pip check
```

2. Installare le dipendenze YourMT3+ mancanti in modo mirato, dopo aver consultato `requirements-studio-yourmt3.txt`; **non eseguire** l'installazione indiscriminata di quel file nell'ambiente ROCm: potrebbe sostituire pacchetti GPU. Salvare `python -m pip freeze` e verificare nuovamente `torch.version.hip` e una piccola operazione GPU. Verificare `pydantic`, `soundfile`, `torchaudio`, `safetensors`, `transformers` e le importazioni richieste dall'originale `model_helper.py`.

3. Installare un nuovo runtime con l'installer ufficiale MTA, approvando la licenza, riutilizzando esplicitamente il Python ROCm in uso. `--test-audio` è un breve WAV musicale autorizzato (non un silenzio):

```
python scripts/install_studio_yourmt3.py \
  --runtime /root/mta-benchmark/yourmt3-reviewed-runtime \
  --test-audio /root/mta-benchmark/yourmt3-smoke.wav \
  --use-current-rocm-python \
  --accept-apache-2-license
```

L'installer scarica SOLO gli asset fissati nel manifesto, ne controlla dimensioni e SHA-256, converte il checkpoint originale in SafeTensors tramite il convertitore ristretto MTA e genera la ricevuta `mta-runtime.json` soltanto dopo un'inferenza riuscita. Può ricevere `--source-cache DIRECTORY` per modalità offline: tutti i file del manifesto, incluso il checkpoint, devono esserci e avere hash corretto. Nessun asset del modello è presente nello ZIP MTA. Per uso ROCm *non* crea una venv CPU e *non* installa né sostituisce PyTorch.

4. Inferenza reale sull'intero MP3 originale (usare il nome effettivo del file):

```
python scripts/run_yourmt3_verified_benchmark.py \
  --runtime /root/mta-benchmark/yourmt3-reviewed-runtime \
  --backend rocm --variant nops \
  --audio '/root/mta-benchmark/All-Night-Long_rec1.MP3' \
  --output /root/mta-benchmark/yourmt3-prediction.json
```

Il runner impone la verifica del runtime e il backend GPU richiesto senza fallback CPU, conserva SHA-256 di input/output e scrive atomicamente un JSON nel medesimo schema `notes` del confronto MR-MT3. Se un'inferenza fallisce, non pubblica output parziali come completi. Il calcolo del modello potrebbe consumare molta memoria GPU: l'operatore deve assicurarsi che nessuna generazione di produzione sia in corso. Questa prova non limita la VRAM per processo né prevede pause e ripresa per singola finestra; eseguirla in una finestra concordata.

5. Valutazione indipendente (i file MIDI non entrano mai nell'inferenza):

```
python scripts/compare_multitrack_models.py \
  --midi '/root/mta-benchmark/All Night Long.MID' \
  --prediction mrmt3=/root/mta-benchmark/mrmt3-results/prediction.json \
  --prediction yourmt3=/root/mta-benchmark/yourmt3-prediction.json \
  --output /root/mta-benchmark/model-comparison.json
python scripts/audit_multitrack_acceptance.py --help
```

Non modificare soglie né scegliere un offset sui dati di riferimento. Conservare manifest, ricevuta runtime, versioni del Python e risultati JSON. Inviare per analisi `yourmt3-prediction.json`, `model-comparison.json` e la ricevuta `mta-runtime.json` (la ricevuta contiene gli hash, non i pesi). **Non attivare il worker di produzione solo per effettuare il benchmark.**

## EN — Verified-run procedure

The new `--use-current-rocm-python` installer flag reuses the operator's previously tested ROCm venv without installing CPU torch. All original-author files and model weights are fixed to the existing source manifest and validated by size/SHA-256, converted to tensor-only SafeTensors, and recorded in an integrity receipt. The benchmark script validates that receipt and the selected GPU backend, then exports strict model predictions independently of the ground truth. Full-song GPU inference and the 10–16 instrument acceptance gate remain **pending real hardware evidence**. For NVIDIA use a separate compatible runtime and `--backend cuda` with the same offline scoring protocol.
