# MTA 0.3.0-r208 — Adapter manifest hardening

Il manifest degli artefatti dei worker AI viene generato soltanto dopo la validazione di tutti gli output. Il file viene scritto nella directory privata mediante file temporaneo (mode 0600), fsync e os.replace sul medesimo filesystem; la directory viene sincronizzata quando il sistema lo supporta. Gli output non devono essere symlink, devono essere file regolari e rispettare nomi sicuri, tipi, limiti dimensionali e unicità.

## Verifiche locali
- `python -m pytest -q tests/test_r208_*.py`: 180 passed.
- `python -m pytest -q tests/test_r208_unified_manifest_atomicity.py tests/test_r207_unified_adapter_and_concurrency.py`: 9 passed.
- Compilazione Python e verifica sintassi `scripts/install_mta.sh`: riuscite.

## Limiti e test in hardware
Non sono stati eseguiti test di inferenza reali su Rocky EL10/ROCm. Restano da validare con i modelli installati i percorsi ACE-Step, Whisper, Demucs, DrumSep, SAM Audio, separazione vocale e analisi accordi, inclusa cancellazione e telemetria CPU/GPU. L'atomicità del manifest non equivale all'atomicità end-to-end di scheduler, pubblicazione audio e billing. Non è stato modificato alcun server.
