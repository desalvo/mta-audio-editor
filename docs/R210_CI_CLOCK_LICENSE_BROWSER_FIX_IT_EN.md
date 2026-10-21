# r210 CI transport/browser regression repair — IT/EN

## IT
Nel job GitHub Actions del 21 ottobre 2026 (logs_107364571849.zip) sono falliti cinque casi: un test host VST3 e quattro parametrizzazioni Playwright. Nessuna regola Ruff o soglia di sicurezza è stata modificata.

1. `tests/test_r210_midi_live.py`: in 7/8 il BPM del progetto misura pulsazioni da ottavo; `MusicalClock` e `TempoMap` convertono correttamente il BPM host VST3 in semiminime al minuto: `123.45 * 4 / 8 = 61.725`. Il test ora verifica il contratto reale, incluso PPQ, senza alterare il timing di produzione.
2. `tests/test_r210_music_assets_browser.py`: prima di cliccare il pannello interno della licenza `madmom`, il test apre esplicitamente il `<details>` contenitore di tutte le licenze. Il precedente `summary.first` apriva invece il pannello commerciale, lasciando il pannello licenze nascosto. Nessuna logica di approvazione o licenza è modificata.

Verifica locale: 26 passati / 5 saltati nei test del clock e VST correlati, e verifica diretta del contesto `61.725, 7, 8`, PPQ `1.02875` a un secondo. I cinque test CI precedentemente falliti restano **da certificare in CI**: il runtime locale manca della libreria `av` e di Chromium Playwright. Quattro test browser sono stati avviati e saltati per assenza del browser. Nessuna inferenza MR-MT3 nuova in questo ciclo.

## EN
The GitHub Actions quality job from October 21, 2026 failed one VST3 host test and four Playwright variants. The 7/8 project BPM uses eighth-note pulses, whereas VST3 host BPM uses quarter notes; the production conversion `123.45 * 4 / 8 = 61.725` is correct, so the test expectation and its PPQ assertion were fixed. The browser test now explicitly expands the parent licenses disclosure before the nested `madmom` disclosure, rather than opening an unrelated first `<summary>`. No licensing guard, production musical timing, global Ruff rule or test threshold was changed. Local related tests: 26 passed, 5 skipped. A final pass of the original five failing tests is pending in CI due to missing local `av` and Chromium.
