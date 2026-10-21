# YourMT3+ GPU preparation / Preparazione YourMT3+ GPU — r210

## Italiano

- Nuova selezione esplicita tramite `MTA_STUDIO_YOURMT3_DEVICE`: `cpu` (predefinito), `rocm`, `cuda`, `gpu`. I dispositivi ROCm usano la stringa interna PyTorch `cuda`.
- Il selettore verifica disponibilità GPU e identità HIP/CUDA e fallisce se il backend richiesto non corrisponde. Non vengono scaricati file né cambiati i pesi.
- **Prerequisito non soddisfatto in questo ambiente:** runtime e checkpoint original-author YourMT3+ con ricevuta SHA verificata (`MTA_STUDIO_YOURMT3_RUNTIME`). Lo script installer CPU esistente non è un installer GPU e non va usato per installare PyTorch sul server MTA.
- Prima di eseguire benchmark su una macchina GPU condivisa, installare in un ambiente Python isolato una build appropriata senza toccare i servizi MTA/Ollama, verificare licenze e ricevuta SHA, autorizzare esplicitamente la finestra di manutenzione. Usare lo stesso audio e MIDI di riferimento e il comparatore a soglie fisse `scripts/compare_multitrack_models.py`.
- Test locali di selezione backend: 14 passati e 1 skip (prova reale opzionale). Ancora **non verificati**: import/forward YourMT3+ su ROCm, qualità del modello e inferenza intero brano. MR-MT3 baseline invariata (F1 9,49%). Commit differito.

## English

- Explicit `MTA_STUDIO_YOURMT3_DEVICE=cpu|rocm|cuda|gpu`; defaults to CPU. ROCm uses PyTorch's `cuda` device namespace.
- Fail-closed backend detection checks accelerator availability and HIP/CUDA identity. No model download or checkpoint mutation.
- **Not present in this environment:** an SHA-receipted, original-author YourMT3+ runtime/weights. The existing CPU installer must not be used to overwrite the production ROCm environment.
- For shared GPU hosts use a separate virtual environment, validated runtime licenses and hashes, an explicit maintenance window, the same reference audio/MIDI, and fixed-threshold `scripts/compare_multitrack_models.py` scoring.
- Focused local selection tests: 14 passed, 1 opt-in real-checkpoint test skipped. Real ROCm forward/full-track YourMT3+ inference and 10–16 instrument accuracy remain unverified. MR-MT3 baseline unchanged (strict F1 9.49%). Commit deferred.
