# MTA Audio Editor 0.3.0-r208 — Adapter hardlink boundary

L’adapter unificato rifiuta sorgenti e artefatti con st_nlink diverso da 1: una path interna al workspace non dimostra da sola che l’inode non sia condiviso fuori dal workspace. Il controllo viene eseguito prima del caricamento dell’adapter e prima della pubblicazione atomica del manifest.

Verifica locale: `PYTHONPATH=. pytest -q tests/test_r208*`: 188 test superati. `python -m compileall -q app` e `bash -n scripts/install_mta.sh` superati.

Limiti: non è una difesa completa contro scritture concorrenti tramite file descriptor già aperti o contro avversari con accesso diretto alla directory di staging. Non certifica GPU/ROCm, ingressi legacy né una transazione ACID unica fra database e filesystem.
