# Voicebank per cantante / Per-singer voicebanks (r210)

IT: Il payload `vocal_synthesis.Settings` accetta `voice_banks: ["air", "cicada", ...]` in ordine corrispondente alle parti MIDI. Se omesso viene impiegato il precedente campo `voicebank`. Si rifiuta una lista con lunghezza diversa dal numero di parti. Ogni voce usa solo banche CC0 controllate, con digest per banca nel manifest di rendering. La selezione nella UI va ancora implementata. Nessuna sintesi neurale è certificata.

EN: `vocal_synthesis.Settings` accepts `voice_banks: ["air", "cicada", ...]` matching MIDI part order. When omitted, legacy `voicebank` is used. Length mismatches are rejected. Each singer uses an independently managed CC0 bank and the output manifest records individual bank hashes. Per-singer bank selection in the UI is not yet connected. Neural synthesis is not certified.
