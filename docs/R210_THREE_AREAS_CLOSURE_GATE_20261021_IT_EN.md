# MTA r210 — gate di chiusura delle tre macroaree / Three-area closure gate

## IT — risultato del ciclo

Versione invariata 0.3.0-r210. Il rendering WAV General MIDI ora scrive in un file temporaneo nella directory di destinazione e pubblica con sostituzione atomica solo dopo il completamento. In caso di errore di sintesi, il file WAV precedente rimane inalterato e il temporaneo viene eliminato. Il comando di benchmark Audio-to-MIDI ora rifiuta target di strumenti fuori dall'intervallo 1–128 invece di produrre una valutazione apparentemente valida.

Prove: `101 passed, 0 failed, 5 skipped, 0 interrupted` nella selezione offline eseguita in questo ciclo (`validation/r210-closure-focused.log`); 3 skip eSpeak e 2 skip runtime/core/banco GM. In un sottoinsieme dedicato: 22 passed. Le prove su file audio sono eseguite con un sintetizzatore test doppio, **non** con un checkpoint neurale o un banco GM reale.

**Sviluppo delle tre macroaree non certificato completamente.** Per chiuderlo occorrono: (1) verifica dei runtime e dei pesi/voicebank/vocoder DiffSinger, RVC, Seed-VC e Transkun con licenze separate; (2) esecuzione di inferenze reali e diagnosi di eventuali errori software; (3) benchmark Audio-to-MIDI su riferimenti multitraccia annotati, senza promesse di 10–16 strumenti; (4) regressione generale controllata con analisi preventiva della richiesta GitHub bloccata, senza aggirare i controlli di rete; (5) ascolto musicale, browser e piattaforme native su hardware target. I gate (1)-(4) potrebbero richiedere ancora sviluppi, non sono automaticamente soli collaudi dell'utente.

Nessuna modifica a produzione/server. Nessun commit/push/tag/release. Conservate le integrazioni AI legacy e l'SDK VST.

## EN — outcome

Version remains 0.3.0-r210. GM WAV rendering now uses a same-directory temporary output and publishes it atomically after successful rendering, preserving the prior file on synthesis failure. Audio-to-MIDI benchmark command rejects impossible instrument targets outside 1–128.

Offline focused suite: **101 passed, 0 failed, 5 skipped, 0 interrupted**; skipped tests need unavailable eSpeak or audited GM/core assets. The output tests use a controlled synth double, not actual checkpoint inference or a reviewed GM bank. Full project regression, licensed checkpoints, musical benchmarks, native/browser acceptance and source-specific licensing remain **uncertified**. See Italian gate above. No real server or Git operations.
