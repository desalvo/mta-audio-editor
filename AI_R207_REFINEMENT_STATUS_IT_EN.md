# MTA Audio Editor 0.3.0-r207 — refinement software / software refinement

## Italiano

Questa revisione mantiene **0.3.0-r207**, senza alcun incremento del build/revisione.

- Il client remoto conserva una singola chiave di idempotenza per richiesta. Dopo perdita di risposta, timeout di connessione o errore HTTP non definitivo prova **una sola GET read-only** su `/api/ai-jobs/request-result/{key}`. Non invia un secondo POST e non avvia mai inferenza locale di ripiego. Per errori espliciti di autenticazione e payload non tenta il recupero. Se il risultato non è già disponibile, segnala un errore: è possibile utilizzare la chiave per recuperarlo più tardi.
- Sono ammessi risultati WAV, ZIP e JSON, con limite trasporto di 32 MiB. I flussi di archivio mantengono le verifiche di nomi, path traversal, tipo, dimensione e WAV/JSON già presenti.
- La cache opzionale (`MTA_AI_RESULT_CACHE_DIR`) mantiene risultati temporanei isolati tramite hash SHA256 di user-id e chiave richiesta. `MTA_AI_RESULT_CACHE_TTL` governa la durata dei risultati (60–604800 secondi, default 86400). Una pulizia opportunistica viene eseguita sui salvataggi, con intervallo configurabile `MTA_AI_RESULT_CACHE_CLEANUP_INTERVAL` (60–86400 secondi, default 3600). È consigliato inoltre un timer esterno per server inattivi: `python -c 'from app.ai_result_cache import purge_expired; print(purge_expired(dry_run=False))'`.
- Gli output temporanei nella cache non vengono fatturati come storage persistente. Solo CPU, secondi GPU certificabili e storage persistente sono voci potenzialmente addebitabili. Energia GPU/VRAM sono diagnostici.
- L'esecuzione su hardware reale, l'attribuzione GPU certificata e la validazione dei binari nativi NON sono state effettuate in questo ambiente. I risultati CI e le dipendenze vanno verificati sui runner previsti prima di qualificare una release per produzione.

## English

This update retains **0.3.0-r207**, without incrementing the revision.

- The remote client uses one idempotency key per inference request. After a lost response, transport timeout or non-terminal HTTP error it attempts **one read-only GET** to `/api/ai-jobs/request-result/{key}`. It never performs a second inference POST or implicitly falls back to local execution. Explicit authentication and invalid-upload failures do not trigger recovery. If no cached result exists, the request fails closed; the key can be used for a later manual recovery.
- WAV, ZIP and JSON results are supported, with a 32 MiB transport limit. Existing ZIP member validation remains in place.
- Optional server result cache: `MTA_AI_RESULT_CACHE_DIR`; configure `MTA_AI_RESULT_CACHE_TTL` in seconds (60–604800; default 86400). Expired entries are opportunistically purged on writes, throttled with `MTA_AI_RESULT_CACHE_CLEANUP_INTERVAL` (60–86400; default 3600). Also schedule an external timer for idle servers: `python -c 'from app.ai_result_cache import purge_expired; print(purge_expired(dry_run=False))'`.
- Temporary replay artifacts are excluded from persistent-storage charges. CPU, trustworthy GPU seconds and persistent storage are the intended billable metrics; GPU energy and VRAM remain diagnostics only.
- Real GPU hardware, native application builds and full CI qualification remain unverified in this environment. Do not interpret these changes as production billing certification.

## Addendum — 11 October 2026 / integrazione controlli accounting e billing

**IT:** Ruff 0.17.0 (`ruff check .`) e Bandit 1.9.4 con i parametri della CI (`bandit -q -r app native scripts/k8s-wizard.py -lll -iii`) superati. Corrette importazioni inutilizzate, rimossi i frammenti SQL condizionali a favore di query esplicite con parametri associati, integrato `Accept: application/json` nel trasporto remoto e aggiunti due test per isolamento per utente e filtri contabili. Suite `tests/test_r207_*`: **186 passed**, 4 warning di deprecazione. Il controllo Bandit più restrittivo (`-ll`) ha ancora **8 segnalazioni di severità media** da revisionare, pertanto non equivale a una revisione completa di sicurezza. Il controllo locale `pip check` rimane negativo per MoviePy 2.2.1 / Pillow 12.3.0. Il coverage totale e tutti i controlli completi della CI non sono certificati; non sono stati eseguiti benchmark GPU o test su hardware reale.

**EN:** Ruff 0.17.0 (`ruff check .`) and Bandit 1.9.4 using the repository CI options (`bandit -q -r app native scripts/k8s-wizard.py -lll -iii`) passed. Removed unused imports, replaced optional SQL string fragments with explicit bound-parameter queries, extended remote `Accept` to include JSON, and added two regression tests for per-user isolation and accounting filters. `tests/test_r207_*`: **186 passed**, four deprecation warnings. The stricter Bandit medium-severity scan (`-ll`) still has **8 findings** requiring review; the CI scan is not a complete security audit. Local `pip check` still fails for MoviePy 2.2.1 / Pillow 12.3.0. Full coverage, overall CI, real hardware and GPU benchmarks remain unverified.

## Refinement r207 — HTTPS/Bandit and local dependencies (2026-10-11)

**IT:** introdotto `app/secure_https.py` con validazione del protocollo HTTPS anche su tutti i redirect; aggiornati i client remoti e i downloader; binding Uvicorn predefinito su `127.0.0.1` (per accesso esterno impostare esplicitamente `MTA_HOST`). Ruff e Bandit `-ll -iii` superati; suite `tests/test_r207_*.py`: 192 superati, 4 avvisi deprecazione. `pip check` nell'ambiente di esecuzione NON è superato: MoviePy 2.2.1 richiede Pillow <12 ma è installato Pillow 12.3.0. La rete PyPI non è accessibile e non sono disponibili wheel compatibili offline. Non sono state falsificate dipendenze né rimossi pacchetti condivisi dell'ambiente. Correggere installando Pillow >=9.2,<12, quindi rieseguire `python -m pip check`.

**EN:** added `app/secure_https.py` enforcing HTTPS-only URLs and redirects; migrated remote transports and downloaders; changed default Uvicorn bind to `127.0.0.1` (set `MTA_HOST` explicitly for external listening). Ruff and Bandit `-ll -iii` passed; `tests/test_r207_*.py`: 192 passed with four deprecation warnings. Local `pip check` is NOT passing: MoviePy 2.2.1 requires Pillow <12 while Pillow 12.3.0 is installed. PyPI access is unavailable and no compatible offline wheel was found. Shared environment packages were not removed or metadata altered. Install Pillow >=9.2,<12 and rerun `python -m pip check`.

## r207 — Accounting and billing transaction finalization (pre-commit)

- Fix shared SQLite connection context to rollback on exceptions, not commit partial changes.
- Lock historical tariff modifications and persistent-storage sample insertion with BEGIN IMMEDIATE, coordinating with atomic billing closure.
- Add concurrent storage-versus-closure, rejected tariff revision, and rollback regression tests.
- Local verification: 195 r207-specific tests passed; Ruff clean; Bandit medium/high clean; pip check clean.
- Full pytest attempted but did not finish (stalled near 25%); CI, coverage certification, GPU benchmarks and native/hardware validation remain pending.

## Italiano — Chiusura transazioni accounting/billing r207

- Corretto il contesto SQLite: rollback su eccezione, evitando commit parziali.
- Serializzati aggiornamenti tariffe e campioni di storage persistente con BEGIN IMMEDIATE rispetto alla chiusura atomica.
- Aggiunti test di regressione per rollback, tariffe rifiutate e concorrenza campionamento/chiusura.
- Verifiche locali: 195 test r207 superati, Ruff, Bandit medio/alto e pip check superati.
- Suite completa non conclusa (arresto ~25%); CI, coverage e collaudi hardware/nativi ancora da eseguire.


## CI coverage follow-up / Correzione coverage CI (2026-10-11)

**IT:** il log GitHub indicava 1707 test passati, 4 skipped e coverage 69,28%, inferiore alla soglia obbligatoria del 70%. Aggiunti 29 test di comportamento per gateway autenticato, adattatori AI e API amministrative di billing; corretto un bug `UnboundLocalError` nella separazione cantanti. I nuovi test e Ruff passano localmente; Bandit con parametri CI passa. Il risultato della suite completa e della coverage aggiornata deve ancora essere verificato in GitHub Actions (non abbassare la soglia).

**EN:** GitHub reported 1707 passing tests, four skips and 69.28% overall coverage against the required 70%. Added 29 behavioral tests for authenticated gateway, AI adapters, and billing administration endpoints; fixed singer-separation `UnboundLocalError`. All new targeted tests and Ruff passed locally; Bandit with CI flags passed. Full-suite results and updated aggregate coverage remain pending GitHub Actions verification; do not lower the threshold.
