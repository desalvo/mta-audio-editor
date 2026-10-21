# DiffSinger – reviewed bank lexicons / Lessici revisionati (r210)

## IT

È disponibile una modalità di associazione sillaba→fonema nativo della voicebank per l'italiano (`it`), il francese (`fr`) e opzionalmente l'inglese (`en`). Non è un sistema G2P generale: **ogni nota deve corrispondere a una sillaba presente nel lessico**, e ciascuna voce del lessico deve produrre esattamente un token fonetico supportato dalla voicebank. Le parole multi-sillabiche devono essere segmentate manualmente prima della richiesta. Nessun lessico o modello viene distribuito automaticamente.

Per usare questa modalità, configurare `MTA_DIFFSINGER_LEXICON` con un percorso assoluto a file JSON regolare non symlink e `MTA_DIFFSINGER_LEXICON_SHA256` con SHA-256 del file. Per l'italiano e il francese la modalità è obbligatoria; per l'inglese è facoltativa tramite `use_reviewed_lexicon: true` nella richiesta. Verificare separatamente la licenza di lessico, checkpoint e vocoder.

Esempio di formato, con token *illustrativi*, **non** una mappatura linguistica validata:

```json
{"schema":"mta-diffsinger-lexicon-1","language":"it","entries":{"sillaba":"TOKEN_COMPATIBILE"}}
```

Non utilizzare l'esempio come dizionario acustico. Il lessico deve essere preparato e convalidato contro l'inventario dei fonemi del modello effettivamente installato. Errori di hash, lingua o sillabe mancanti causano rifiuto dell'inferenza. L'interfaccia corrente può richiedere inserimento delle sillabe già segmentate; non è ancora un editor generale di testo cantato con sillabazione automatica.

## EN

An optional checkpoint-pinned, bank-specific **one-note/one-token** lyric lexicon is supported for Italian (`it`), French (`fr`) and opt-in English (`en`). It is **not** general-purpose grapheme-to-phoneme inference. Each score note must contain one reviewed syllable in the lexicon, mapped to exactly one bank-compatible phoneme token; multisyllabic words must be manually segmented. No models or lexicons are bundled.

Provide `MTA_DIFFSINGER_LEXICON` (absolute JSON path) and `MTA_DIFFSINGER_LEXICON_SHA256` (file digest). IT and FR require a pinned lexicon; EN opts in using `use_reviewed_lexicon: true`. The sample format above is illustrative only, and not a usable pronunciation dictionary. Operators must separately review the lexicon, acoustic-model and vocoder licenses. Any unmatched syllable or integrity mismatch fails closed.
