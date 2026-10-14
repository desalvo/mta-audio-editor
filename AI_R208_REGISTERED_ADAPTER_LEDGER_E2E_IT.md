# r208 — Ledger end-to-end per i sette adapter registrati

Ciclo 14 ottobre 2026, versione invariata 0.3.0-r208.

## Perimetro verificato

`execute_registered_worker` per whisper, chords-ml, demucs, drumsep, sam-audio, singer-separation, backing-vocals: avvio reale di subprocess amministrato (simulatore deterministico, non modelli di produzione), input WAV confinato, risultato validato in ZIP manifest, misurazione CPU del processo, finalizzazione nel database contabile reale; ogni risultato non introduce metriche GPU non attestate. 7 scenari distinti con database reale.

Nuova barriera: una cancellazione intervenuta durante il packaging non finalizza il job come `done` e non pubblica il risultato. Test dedicato sul passaggio package -> finalizzazione.

## Limiti ancora aperti

Questa certificazione prova il percorso *server-side* di registrazione contabile degli adapter con worker subprocess simulati, non l'esecuzione dei modelli reali ROCm né l'intero flusso dai client nativi. Non dimostra idempotenza universale della creazione dei job senza idempotency key, né misurazioni GPU per job. Gli errori dopo la finalizzazione del ledger ma prima della consegna HTTP richiedono gestione specifica di recovery/receipt: non dichiarare completo quel caso sulla base di questa suite.

## Test

`PYTHONPATH=. pytest -q tests/test_r208* tests/test_r207_billing_metering.py` -> 834 passed, 9 warnings (local). Nessuna modifica effettuata su infrastruttura remota o repository Git.
