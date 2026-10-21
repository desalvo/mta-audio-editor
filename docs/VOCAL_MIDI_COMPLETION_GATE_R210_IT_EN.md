# Vocal Studio / Audio-to-MIDI completion gate — 2026-10-20

## IT — Risultati verificati
- Vocal Studio: la sequenza delle sillabe segue l'identità della nota anche se le note MIDI sono presentate fuori ordine cronologico.
- Validazione preventiva di melodie vuote, note sovrapposte per cantante e regioni oltre dieci minuti, prima del caricamento di voicebank.
- Conservati voice_syllables indipendenti, compatibilità sillabe legacy, e la pipeline OddVoices CC0.
- Test mirati: 26 superati, 1 saltato (voicebank reale assente).
- Audio-to-MIDI: regressione mirata per riconciliazione esistente, senza nuovo modello né dimostrazione di 10–16 strumenti da mix completo.

## IT — Bloccanti per chiusura end-to-end
- Backend neurale di canto autorizzato, phonemizer IT/EN/FR, UI espressiva e conversione timbrica da implementare/validare.
- Trascrizione multistrumento 10–16 sorgenti da mix completo, ensemble di modelli multipli, accuratezza su dataset annotati e valutazioni per strumento da dimostrare.
- Test completi su Windows/macOS/Linux, AMD ROCm, voicebank/checkpoint reali e regressione integrale ancora necessari.
- Questa consegna e' un avanzamento, non una certificazione di completamento delle due macroaree.

## EN — Verified results
- Vocal syllables retain their original note pairing when the incoming MIDI note list is unsorted.
- Empty, overlapping, and overlong singer parts are rejected before loading voicebanks.
- Independent voice syllables and legacy compatibility remain intact.
- Targeted suite: 26 passed, 1 skipped due to unavailable installed voicebank.
- Existing Audio-to-MIDI reconciliation tested; no newly integrated transcription model or 10–16 instrument benchmark.

## EN — Outstanding completion gates
- Licensed neural singing backend, IT/EN/FR phonemization, expressive UI, voice conversion and real model evaluation.
- Demonstrated 10–16 independent instruments transcribed from full mixes with metrics on annotated real audio.
- Native platform/ROCm trials and full regression. Do not mark the macroareas as complete without these results.
