# DiffSinger direct CLI bridge — r210

## Italiano

Il backend `diffsinger` utilizza **realmente** il comando OpenVPI `scripts/infer.py acoustic`, creando un file `.ds` (fonemi, note e durate), eseguendo il vocoder configurato in DiffSinger e importando l'output WAV mono 48 kHz. Supporta parti indipendenti; i checkpoint **non** sono inclusi in MTA.

Prerequisiti amministrativi:
- Distribuzione DiffSinger/OpenVPI verificata e installata in `MTA_DIFFSINGER_ROOT`; `scripts/infer.py` deve esistere.
- Interprete Python dedicato e pin SHA-256 `MTA_DIFFSINGER_PYTHON`, `MTA_DIFFSINGER_PYTHON_SHA256`.
- Esperimento acustico installato in `checkpoints/<MTA_DIFFSINGER_EXPERIMENT>`; percorso e SHA-256 del checkpoint dichiarati mediante `MTA_NEURAL_SINGER_CHECKPOINT` e `MTA_NEURAL_SINGER_SHA256`.
- Vocoder configurato nell'esperimento e SHA-256 `MTA_DIFFSINGER_VOCODER`, `MTA_DIFFSINGER_VOCODER_SHA256`.
- Identità del modello registrata e autorizzata in `MTA_NEURAL_SINGER_POLICY_MODEL`.

**Licenze:** il codice OpenVPI è Apache-2.0, ma ogni modello acustico/voicebank/vocoder richiede verifiche separate. I vocoder comunitari comuni sono CC BY-NC-SA 4.0: non abilitarli nel servizio commerciale senza diritti aggiuntivi. Nessuna licenza è concessa dall'accettazione dei rischi.

Il bridge richiede un fonema compatibile con il dizionario della voicebank *per nota*; non implementa conversione grafemi→fonemi e rifiuta input non supportati. La sintesi non è stata eseguita con checkpoint reale in questo ambiente. Bisogna ancora validare pronuncia multilingue, qualità espressiva, GPU ROCm, installazione native e conversione timbrica. La funzionalità rimane **integrazione tecnica testata, non macroarea conclusa**.

## English

Backend `diffsinger` invokes actual OpenVPI `scripts/infer.py acoustic` with a generated `.ds` score, verifies operator-provided acoustic and vocoder assets, and imports validated 48 kHz mono WAV output. No weights are bundled. Specify `MTA_DIFFSINGER_ROOT`, `MTA_DIFFSINGER_PYTHON`, `MTA_DIFFSINGER_PYTHON_SHA256`, `MTA_DIFFSINGER_EXPERIMENT`, `MTA_DIFFSINGER_VOCODER`, `MTA_DIFFSINGER_VOCODER_SHA256`, `MTA_NEURAL_SINGER_CHECKPOINT`, `MTA_NEURAL_SINGER_SHA256` and `MTA_NEURAL_SINGER_POLICY_MODEL`.

Provide voicebank-compatible phonemes for every note: this integration does not claim multilingual grapheme-to-phoneme conversion. The operator must independently clear each acoustic model, singer bank and vocoder. OpenVPI community vocoder weights are CC BY-NC-SA 4.0; commercial licensing must not be inferred from the code license. Real checkpoint inference, ROCm, pronunciation and audio quality remain unverified.

## Sources
- https://github.com/openvpi/DiffSinger/blob/main/scripts/infer.py
- https://github.com/openvpi/DiffSinger/blob/main/docs/GettingStarted.md
- https://openvpi.github.io/vocoders/

## Additional runtime checks / Controlli aggiuntivi del runtime (2026-10-20)

IT: il checkpoint acustico con hash verificato deve trovarsi dentro `checkpoints/<esperimento>/` del runtime DiffSinger selezionato. Output con frequenze di campionamento non ragionevoli o durate incompatibili con lo spartito vengono rifiutati. Questi controlli non sostituiscono una prova reale con un modello, un vocoder e una voicebank autorizzati. Non è consentito considerare la semplice presenza del vocoder sul filesystem una prova del suo effettivo utilizzo nella configurazione del motore.

EN: the hash-pinned acoustic checkpoint must reside inside `checkpoints/<experiment>/` of the selected DiffSinger runtime. Outputs with implausible sample rates or durations inconsistent with the score are rejected. These checks are not a substitute for inference with a real licensed model, vocoder, and voicebank. A vocoder file existing on disk does not establish that the DiffSinger experiment configuration actually references it.
