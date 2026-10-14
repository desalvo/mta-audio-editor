# CI r208 — timeout esteso

Il job `quality` della pipeline `.github/workflows/ci-cd.yml` ha un timeout complessivo di **150 minuti** (precedentemente 120). La fase `pytest` viene eseguita con GNU `timeout` per **140 minuti**, inviando SIGTERM e concedendo ulteriori 120 secondi prima di SIGKILL. Il margine residuo serve alle fasi di compilazione, convalida audio, lint, PDF e upload coverage.

Non cambia VERSION/REVISION e non si modifica il budget dei job indipendenti. Il timeout esteso non costituisce certificazione di regressione: verificare gli esiti effettivi di GitHub Actions e completare i collaudi hardware separatamente.
