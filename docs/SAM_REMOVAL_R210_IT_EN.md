# Rimozione SAM Audio / SAM Audio retirement — r210

SAM Audio e la separazione di singoli cantanti sono rimossi da runtime, cataloghi, licenze attive, menu nativi, bundle e strumenti di installazione. Demucs standard rimane il default; le opzioni percussioni sono esplicite. DSP e Mega53 conservano i controlli esistenti. DrumSep non riceve alcuna nuova autorizzazione sui pesi.

Legacy API, saved native settings, queued jobs, model aliases and extension registrations cannot reactivate the retired kinds. They fail before source processing, model startup, output publication or configuration writes. Missing percussion-method fields in ordinary old queued Demucs work still mean DSP; a retired selected method is never silently replaced.

The two retired Python entrypoints are deleted. Successful setup strips only their obsolete environment bindings and preserves unrelated settings. Existing history, diagnostics, resource ledger and runtime garbage-collection protections are retained. Historical validation archives are not current operational instructions.

Operational setup documents now record retirement, the original service environment and the historical Hugging Face authentication failure. Administrator HTML/PDF chapters describe the supported direct percussion validation workflow. See PERCUSSION_BENCHMARK_PROTOCOL.md and PERCUSSION_SEPARATION_MODELS.md.

Software regressions cover actual API rejection before side effects, queued work, reserved extension names, native settings, installer cleanup, catalog absence and preference migration. They do not establish real-model inference, audio quality, GPU billing verification or deployment certification. No checkpoint permission, professional approval or production operation is created by this change.
