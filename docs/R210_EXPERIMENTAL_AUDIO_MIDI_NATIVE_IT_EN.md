# Experimental Audio-to-MIDI engines / Motori sperimentali Audio-to-MIDI

## IT
Le interfacce Studio condivise dal server e dalle applicazioni native presentano MR-MT3 e YourMT3+ come sperimentali. I motori sono selezionabili soltanto quando le API di capacità della destinazione confermano la disponibilità del runtime. I checkpoint hanno provenienza, licenza e integrità da verificare indipendentemente. La schermata di amministrazione visualizza lo stato e le licenze; il caricamento di un pacchetto di asset gestiti non configura automaticamente un runtime MT3. Per l'installazione del runtime seguire la procedura verificata, separata per piattaforma. L'inferenza non certifica l'accuratezza 10–16 strumenti. Il valutatore di fedeltà 0–100 richiede MIDI di riferimento, non utilizza audio da solo come ground truth, e non può attribuire un punteggio valido senza riferimento. Non inferire 100 dalla sola presenza di 10 tracce.

## EN
Studio interfaces shared by server and native applications expose MR-MT3 and YourMT3+ as experimental. Engines are selectable only if the target device capabilities report their runtime available. Checkpoint rights, provenance and integrity must be independently validated. Model administration displays readiness and license links; uploading a managed asset bundle does not itself configure an MT3 engine runtime. Follow the platform-specific reviewed installation procedure. Successful inference does not certify 10–16-instrument accuracy. The 0–100 fidelity scorer requires a reference MIDI, not audio alone as ground truth, and must not report a valid score without it. Do not infer perfect fidelity from the mere presence of ten tracks.

## Verification / Verifica
- Syntax checks: `node --check app/static/studio_extended.js` and `node --check app/static/ai_studio.js`.
- Focused pytest: `tests/test_r210_experimental_native_engine_ui.py`, `tests/test_r210_experimental_fidelity_score.py`.
- Still pending: native GUI build/device testing, complete CI, real hardware runtimes per platform and quantitative model accuracy.
