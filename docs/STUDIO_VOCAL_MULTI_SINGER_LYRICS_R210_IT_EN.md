# MTA r210 — Independent singer lyrics / Testi indipendenti per cantante

## Italiano
Vocal Studio, backend OddVoices: il campo opzionale `voice_syllables` contiene una lista di sillabe o fonemi per ciascuna parte vocale MIDI, mantenendo l'ordine delle parti. Il numero di liste deve coincidere con il numero di cantanti; ciascuna lista deve contenere una voce per ogni nota della rispettiva parte quando `language=en`. È compatibile con il vecchio campo `syllables`, usato in assenza di `voice_syllables`. L'allineamento viene controllato prima del caricamento della voicebank. Esempio per due parti rispettivamente con tre e una nota:

```json
{"language":"en","voicebank":"air","voice_syllables":[["la","la","la"],["ah"]]}
```

Non è fonemizzazione automatica, non introduce nuove lingue e non fornisce canto neurale. Le voicebank verificate restano requisiti esterni.

## English
Vocal Studio with the OddVoices backend now accepts `voice_syllables`: one list of syllables or phonemes for every ordered MIDI vocal part. Each list must match that singer's note count for `language=en`. The legacy shared `syllables` setting remains valid when `voice_syllables` is omitted. Alignment validation occurs before loading voicebank assets.

This does not add automatic phonemization, new languages, or neural singing. Reviewed voicebanks remain separately installed prerequisites.

## Evidence and limits
- `tests/test_r210_vocal_multisinger_lyrics.py` covers differing note counts, backward compatibility and rejection paths.
- Targeted regression: 24 passed, 1 skipped (requires a real installed voicebank); no production server or ROCm inference.
- Multi-Track Audio-to-MIDI remains partially complete: two-model reconciliation and isolated-source inference exist, but accurate 10–16 instrument separation from a full mix is not certified.
