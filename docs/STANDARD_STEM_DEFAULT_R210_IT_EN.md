# Separazione standard Demucs / Standard Demucs separation

## Italiano

Baseline del commit utente: `f235f4c3ca67af72006bfc6262474ccb0ff0a705`.

La preferenza persistente `mta.stem.target` poteva riaprire entrambe le finestre su “Solo percussioni” pur lasciando deselezionata la casella drums/percussioni. Il server interpretava correttamente quel target come richiesta esplicita, attivando il secondo passaggio e pubblicando soltanto le percussioni. La selezione persistente non viene più ripristinata nelle finestre né aggiornata dalle scelte di separazione; un eventuale valore legacy rimane ininfluente.

Ogni apertura di “Importa brano e separa strumenti” o “Separa traccia” parte da tutti gli stem standard Demucs, con percussioni disattivate. Modello e numero di stem Demucs mantengono i rispettivi controlli esistenti. Il metodo delle percussioni può essere ricordato, ma rimane nascosto e disabilitato finché non richiesto; il payload standard usa `stem_targets=all`, `split_percussions=false`, `percussion_method=dsp`, senza passaggio DSP aggiuntivo.

Per attivare le percussioni si spunta la casella oppure si sceglie esplicitamente un target percussivo. Tornando al target “Tutti gli stem standard (Demucs)” si disattiva la casella; togliendo la spunta viene cancellato anche un target percussivo residuo. La normalizzazione viene ripetuta all'invio. La selezione “Tutti” con casella attiva continua a richiedere tutti gli stem e il secondo passaggio; i target voce principale e Other restano disponibili senza attivare le percussioni.

Nessun backend Python modificato. La revisione delle nuove scelte UI e dei due payload conserva le 794 voci dell'inventario di esecuzione e aggiorna soltanto il binding di `app/static/app.js`; checker, prove, classificazioni e controlli di licenza/ammissione/misurazione restano invariati. Il tag cache JavaScript viene aggiornato per distribuire la correzione ai client esistenti.

Superati **179 test, zero fallimenti/errori/skip**, inclusi **36 nuovi casi**: 18 esercitano le funzioni JavaScript applicative delle due finestre e i payload, 16 verificano pubblicazione API locale/remota con quattro metodi percussivi inattivi e due verificano il secondo passaggio esplicitamente richiesto. Ruff e sintassi JavaScript passano. Le verifiche e i limiti correnti sono registrati in `validation/r210-standard-stem-default-result.json` e nel relativo XML. I test creano audio sintetico WAV/MP3 ed eseguono richieste API e pubblicazione in progetto con inferenza sostituita da fixture. Non costituiscono una prova di inferenza neurale reale, rendering browser, app nativa o nuova CI remota verde.

RC generale invariata: **34/42 = 81,0%, PRE-RC**. Nessun commit, push, deployment o accesso ai server reali.

## English

Both separation dialogs now start with all standard Demucs stems and percussion processing off. A persisted selective target can no longer silently enable the percussion pass or discard the standard stems. The remembered percussion model is inactive until a fresh explicit choice; standard requests use `all`, `false`, and the neutral `dsp` method, which does not run an additional DSP pass.

Selecting a percussion target enables its checkbox. Unchecking it clears any remaining percussion target, and selecting all standard stems turns percussion processing off. Submission repeats this normalization. Explicit percussion and other selective workflows remain available. The JavaScript cache tag is refreshed.

Backend execution and security policies are unchanged. The execution review preserves all 794 boundary entries and binds the reviewed JavaScript bytes. Evidence uses production JavaScript functions and real synthetic audio through API/publication fixtures with mocked inference. Real-model, browser/native visual and remote CI acceptance are not claimed. RC remains **34/42 = 81.0%**.
