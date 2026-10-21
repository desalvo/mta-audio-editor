# MVSep Mega 53 — Lead / Backing Vocals (IT / EN)

## IT — stato e installazione

**Stato**: adattatore implementato (server e percorso nativo); modello AI reale NON testato. Versione 0.3.0-r210 invariata. UVR KARA 2 e gli altri precedenti motori restano registrati come legacy e non sono stati eliminati. Il motore Mega 53 è bloccato dalla policy fino a verifica e autorizzazione amministrativa riferita al checkpoint esatto. La licenza MIT riportata dal progetto non è un'autorizzazione generale sui dati di training.

Installare separatamente il repository ufficiale `https://github.com/ZFTurbo/Music-Source-Separation-Training`, le dipendenze, il **config YAML corrispondente al modello Mega 53** e il checkpoint esatto della release `v1.0.21`, senza includere pesi nel pacchetto MTA. Verificare l'hash del download, la licenza dei pesi e le condizioni d'uso. Configurare percorsi assoluti:

```
MTA_MEGA53_ROOT=/opt/msst
MTA_MEGA53_CONFIG=/opt/msst/configs/<mega53-config>.yaml
MTA_MEGA53_CHECKPOINT=/var/lib/mta/models/mega53/<authorized-checkpoint>.ckpt
MTA_MEGA53_PYTHON=/opt/msst-venv/bin/python
MTA_LEAD_BACKING_DEFAULT_MODEL=mvsep-mega53
```

I nomi fra parentesi angolari sono SEGNAPOSTO, non percorsi verificati. Non sostituire il file di configurazione con una config generica BS-RoFormer. La procedura richiede il comando `inference.py` dell'upstream che accetta `--model_type bs_roformer`, `--config_path`, `--start_check_point`, `--input_folder`, `--store_dir`. I percorsi assoluti devono puntare a file regolari esistenti. L'adattatore verifica che vengano prodotti esattamente uno stem `lead-vocal` e uno `back-vocal`, poi li pubblica come `lead_vocals.wav` e `backing_vocals.wav`; errori o ambiguità causano rifiuto senza fallback nascosti. Il modello è oneroso: l'autore consiglia almeno 16 GB di VRAM. L'esecuzione reale AMD ROCm è da verificare. Gli output del modello 53-stems possono sovrapporsi e non sommare al mix originale.

**Importante**: il modello non viene scaricato automaticamente. Selezionare il modello in MTA solo dopo l'installazione e la verifica della policy; l'adattatore non è una prova di autorizzazione commerciale. La modalità non commerciale non autorizza checkpoint dalla licenza sconosciuta. I controlli su crediti, token, code e billing richiedono collaudi end-to-end. Per confronto reale usare brani con stem di riferimento separati di lead/backing, calcolare SDR/SI-SDR, leakage, RTF, picco RAM/VRAM e valutazione ascolto ABX contro UVR KARA 2 *solo se il checkpoint UVR è autorizzato*. Nessuno di questi risultati è stato misurato nel presente ciclo.

## EN — status and setup

**Status**: local/server adapter implemented, actual neural inference NOT tested. MTA remains 0.3.0-r210. Existing UVR/other integrations remain available as disabled legacy options. The Mega 53 policy defaults to disabled until the operator reviews the specific checkpoint and documents permission. Upstream MIT claims do not resolve training-data provenance.

Install the upstream MSST repo, its dependencies, the matching Mega 53 configuration, and the exact release v1.0.21 weights outside MTA. Supply the absolute environment paths shown above. The integration runs upstream `inference.py` without a shell, insists on uniquely identified `lead-vocal` and `back-vocal` WAV outputs, and never silently substitutes an alternative model. Minimum 16GB VRAM is suggested upstream; AMD ROCm must be validated. Outputs can overlap. No real audio quality or speed measurements have been performed; the included automated tests exercise only the adapter contract with a synthetic inference stub.

References: https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/tag/v1.0.21 and https://github.com/ZFTurbo/Music-Source-Separation-Training
