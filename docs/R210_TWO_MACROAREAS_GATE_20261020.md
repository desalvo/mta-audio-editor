# MTA 0.3.0-r210 — Two bounded completion gates / Due chiusure circoscritte

## Italiano

1. Vocal Studio — validazione budget aggregato: l'ammissione rifiuta più di 40.000 note sommate su tutte le parti prima di caricare voicebank o eseguire la sintesi. Il limite per parte e la verifica del testo indipendente rimangono attivi.
2. Audio-to-MIDI — riconciliazione unisoni: due parti distinte con lo stesso programma GM non possono essere risolte sulla sola uguaglianza di nota/tempo. Gli eventi restano esplicitamente ambigui ed editabili, invece di assegnarli arbitrariamente a un performer.

Test mirati: 21 passed, 1 skipped (voicebank compilata non disponibile). **NON** equivale al completamento delle due macroaree globali. Rimangono sintesi neurale, fonemizzazione IT/FR, voice conversion, trascrizione affidabile del mix su 10–16 strumenti, prove GPU/ROCm, test native, benchmark musicali e regressione integrale.

## English

1. Vocal Studio — aggregate note admission budget: refuse more than 40,000 notes across all singers before voicebank loading and synthesis; existing per-part and independent-lyrics validation remains.
2. Audio-to-MIDI — same-program unison ambiguity: two performers sharing a GM program cannot be assigned deterministically solely by onset/pitch. Preserve events as ambiguous, editable hypotheses rather than silently attributing them to one performer.

Targeted tests: 21 passed, 1 skipped (compiled voicebank unavailable). These are **two bounded engineering closures, NOT completion of the two overall product macroareas**. Neural synthesis, IT/FR phonemization, voice conversion, reliable 10–16 instrument full-mix inference, ROCm/native validation, musical benchmarks and full regression remain pending.
