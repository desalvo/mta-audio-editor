# Merchant history Chromium CI correction — 2026-10-25 — PRE-RC

## Italiano

Base verificata: commit `adca7fe7bd0ab8296e8075cbb2887799e73aa120`.
Run osservato: https://github.com/desalvo/mta-audio-editor/actions/runs/40146207457/job/121027981814

La precedente correzione YAML è applicata: installazione dipendenze e Chromium
riuscite. Il report originale contiene quattro fallimenti, zero test superati,
zero saltati. Tutti si fermano su `Locator.fill: Error: Malformed value` per
`2026-09-01T00:00:00`. Playwright 1.51 assegna il valore e confronta la stringa
restituita dal campo; Chromium elimina i secondi a zero. Nel log compare anche
`Payment outbox review unavailable`: il database isolato della fixture non
aveva lo schema outbox creato normalmente al primo checkout.

Correzioni limitate al collaudo:

- Date in forma canonica al minuto; verifica che le due vere richieste al
  provider sintetico ricevano ancora gli esatti timestamp UTC con secondi.
- Fixture condivisa con TestClient reale, sessione amministratore reale e
  tabella outbox vuota costruita dallo schema applicativo. Nessun endpoint
  simulato, nessun controllo HTTP 200 rimosso, nessun ordine creato.
- Verifica locale delle sei letture iniziali del pannello, senza Chromium.
- In caso di errore il runner mostra gli ultimi 20.000 byte del log Pytest
  e conserva il log completo nell'artefatto. Anche un timeout scrive
  `accepted:false`; un precedente XML non può soddisfare il nuovo run.

Validazione locale: 12 test superati (9 gate esistenti, 3 nuovi), Ruff e
compilazione Python riusciti; raccolti esattamente i quattro casi Chromium.
Nessun eseguibile Chromium disponibile localmente: questi quattro casi
corretti devono ancora essere eseguiti nella CI. Non sono dichiarati superati.
Applicazione, workflow, pagamenti e criteri RC non sono modificati.

Applicazione della patch dalla radice del repository, dopo averla scaricata:

```sh
git apply --check /percorso/MTA-r210-merchant-chromium-ci-fix.patch
git apply /percorso/MTA-r210-merchant-chromium-ci-fix.patch
MTA_TEST_OFFLINE=1 PYTHONPATH=. python -m pytest -q tests/test_r210_merchant_chromium_harness.py tests/test_r210_merchant_chromium_gate.py
```

Il commit e il dispatch restano a cura dell'utente. Messaggio suggerito:
`Fix Chromium merchant history date input, fixture setup and failure diagnostics`.
Avviare **Optional merchant history Chromium** sul nuovo commit con
**merchant_history_chromium=true**. Rieseguire il vecchio run conserverebbe
il codice difettoso. Occorrono quattro pass, zero failure/error/skip e
`acceptance.json` con `accepted:true` legato al nuovo SHA in `runtime.json`.
Inviare il link del nuovo run per la verifica. Nessun commit, push o dispatch
è stato eseguito qui; nessun nuovo ZIP cumulativo.

Progresso formale invariato: **23/42 (54,8%), 0/7 macroaree; RC falsa e
cambio di regime disabilitato**. Questi test riguardano il solo storico
merchant con provider sintetico, non pagamenti reali né accettazione globale.

## English

The linked run used the verified base SHA above. Chromium installed and
launched, but all four cases failed on a noncanonical datetime-local fill
value. The isolated database also lacked the lazily created empty payment
outbox. The patch fixes only the test harness and runner diagnostics, keeps
real HTTP/API assertions and the strict four-pass/zero-skip gate, and adds a
real API preflight plus subprocess failure/timeout regressions.

Twelve local checks pass; the corrected four browser cases await a new manual
CI dispatch on the user's new commit. No repository write or dispatch was
performed. Apply the patch with the commands above and dispatch the same
workflow with its opt-in input enabled. The acceptance result must bind to the
new commit. RC progress and all money/transition restrictions remain unchanged.

## Evidence and primary source

- Original artifact: https://github.com/desalvo/mta-audio-editor/actions/runs/40146207457/artifacts/12581146539
- Downloaded ZIP SHA256: `a5be712c10902e17bf90c6dcb32bfbfef0cff0ead2184861d07d74b64046daa8`.
- Original `runtime.json` matches the local application, admin panel and
  corrected YAML hashes. Both parent test/runner files also match the
  repository bytes at the verified base SHA.
- Playwright 1.51 fill implementation:
  https://github.com/microsoft/playwright/blob/v1.51.0/packages/playwright-core/src/server/injected/injectedScript.ts
- Full original CI artifacts retained in
  `docs/validation/r210/merchant-history-ci-40146207457/` in the working
  checkpoint; not duplicated in the small delivery patch. They remain
  downloadable from the original run above.
