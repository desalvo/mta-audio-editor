# MTA 0.3.0-r208 — correzioni CI dopo commit su main

## Modifiche
- DEB: il worker ACE-Step opzionale non è presente nel fixture minimale; chmod condizionato alla sua presenza, mantenendo obbligo release-ready.
- Repository APT: `python3` installato nel container CI e controllato prima del test di indicizzazione firmata.
- Ruff: import inutilizzati rimossi nei moduli e test segnalati; eliminati assegnamenti inutilizzati; sostituiti percorsi `/tmp` fissi nei test con `tmp_path`; eccezioni billing outbox non più silenziate con `pass`; annotati controlli di query SQL composte da clausole fisse e valori parametrizzati e URL client HTTPS vincolati.

## Test locali
- `tests/test_server_native_packaging_208.py`: 7 passed.
- Smoke build DEB fixture + verify_native_installers.py: OK.
- Regressione mirata progetto/planning/locking: 21 passed, 8 warnings.
- `compileall` app + tests: OK.
- Regressione r208 globale: avanzata all’82%, poi timeout, quindi NON certificata.
- Ruff non eseguibile nell'ambiente locale (non installato né scaricabile): eseguire `ruff check app native tests scripts/k8s-wizard.py` su GitHub Actions.

## Prossimo passaggio
Applicare il contenuto di questo ZIP sul repository, eseguire commit e controllare le tre workflow fallite. Non sono stati eseguiti commit, push, tag o release dal sistema di sviluppo. Versione 0.3.0-r208 invariata.
