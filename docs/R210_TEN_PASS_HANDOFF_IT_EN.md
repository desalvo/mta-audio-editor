# r210 ten-pass engineering handoff / Consegna tecnica dieci passaggi

## IT
- Versione invariata: 0.3.0-r210. Nessuna operazione Git/server.
- Dieci passaggi documentati in `DEVELOPMENT_STATUS.md`; migliorati controlli PCM Vocal Studio e robustezza del renderer General MIDI.
- Suite trasversale offline: 214 superati, 0 falliti, 14 saltati. Test focalizzati (inclusi nel totale): 64 superati.
- **Non certificato:** inferenze reali DiffSinger/Seed-VC/RVC/Transkun, accuratezza multitraccia 10–16 strumenti, ascolto GM, accettazione browser e native, regressione generale. Il passaggio esclusivamente ai collaudi utente non è ancora dimostrato.
- Operatore: installare soltanto voicebank/checkpoint/vocoder/soundfont con licenze individualmente verificate; raccogliere log di inferenze e benchmark di riferimento, collaudare rendering GM, audio MIDI e UI. Non è necessaria una modifica al server per le sole correzioni locali di questo ciclo; il deploy del nuovo codice richiede normale procedura di staging.

## EN
- Version remains 0.3.0-r210, without Git or production server actions.
- Ten passes recorded in `DEVELOPMENT_STATUS.md`; tightened Vocal Studio PCM and isolated GM rendering checks.
- Offline cross-area suite: 214 passed, 0 failed, 14 skipped; focused subset (included): 64 passed.
- **Uncertified:** actual licensed DiffSinger/Seed-VC/RVC/Transkun inference, 10–16 instrument multitrack benchmarks, GM listening, browser/native acceptance and full repository regression. These can reveal additional software defects.
- Operator: install only individually licensed/pinned model, vocoder, voicebank and soundfont assets; capture genuine inference/benchmark evidence and validate GM/native/browser paths. No server change is needed merely for the local corrections; staging deployment requires the normal procedure.
