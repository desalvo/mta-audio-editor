# R210 — Chiusura tecnica / Engineering closure

## Italiano
Questo pacchetto contiene la correzione della convalida PCM di Vocal Studio e la regressione offline selezionata (104 superati, 0 falliti, 4 saltati). Non costituisce attestazione di inferenza reale né di chiusura end-to-end delle tre macroaree. Per il collaudo sul server: usare bundle e checkpoint con hash e licenze autorizzate; verificare separatamente codice, vocoder, voicebank, modelli ausiliari e SoundFont; eseguire DiffSinger, RVC, Seed-VC, Transkun e il benchmark musicale etichettato; collaudare il MIDI GM su hardware, browser e client nativi. La regressione completa è ancora necessaria, senza richieste GitHub non autorizzate. Nessun deploy o commit è stato eseguito.

## English
This build tightens Vocal Studio PCM validation and records an offline cross-area regression (104 passed, 0 failed, 4 skipped). It does not certify real neural inference or end-to-end completion of the three areas. On the target server, install only hash-pinned and licensed assets; separately verify code, checkpoint, vocoder, voicebank, auxiliary models and SoundFont rights; exercise DiffSinger, RVC, Seed-VC and Transkun with real models; run labeled musical benchmarks and GM native/browser/hardware acceptance. A full repository regression still needs a network-governed environment. No deployment or Git operation took place.
