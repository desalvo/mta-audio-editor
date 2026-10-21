# External Neural Singing — 0.3.0-r210

## IT
Introdotto il contratto `neural-external` per il render per cantante. Non comprende pesi, non installa DiffSinger e non rappresenta una sintesi neurale certificata: e' necessario un adattatore reale installato dall'amministratore che accetti `--request <json> --output <wav>` e generi WAV mono PCM, 48 kHz. Le note nel JSON hanno `pitch`, `start_ms`, `duration_ms`, `velocity`, `syllable`. L'adattatore deve controllare fonemi, lingue, licenze del modello e compatibilita' della voicebank.

Variabili: `MTA_NEURAL_SINGER_EXECUTABLE` (file eseguibile locale assoluto), `MTA_NEURAL_SINGER_CHECKPOINT` (file regolare assoluto), `MTA_NEURAL_SINGER_SHA256` (hash reale del checkpoint), `MTA_NEURAL_SINGER_POLICY_MODEL` (id registrato della policy, ad esempio modello con autorizzazione amministrativa). Il codice verifica hash, assenza di symlink e policy prima di eseguire. Nessun download implicito. Non selezionare il backend senza autorizzazione applicabile e senza collaudo del runtime.

## EN
An optional `neural-external` per-singer output contract is available. No neural weights or DiffSinger model are bundled or installed. An operator-installed binary must accept `--request <json> --output <wav>` and generate a mono 48 kHz WAV file. JSON notes contain `pitch`, `start_ms`, `duration_ms`, `velocity`, and `syllable`. The operator adapter is responsible for phonemization, language coverage and model/voicebank compatibility.

Deployment variables: `MTA_NEURAL_SINGER_EXECUTABLE` (absolute executable), `MTA_NEURAL_SINGER_CHECKPOINT` (absolute regular file), `MTA_NEURAL_SINGER_SHA256` (actual checkpoint digest) and `MTA_NEURAL_SINGER_POLICY_MODEL` (registered policy identity). Integrity, symlink protection and license policy are checked before inference. No silent model download occurs. A fully working neural runtime and real inference benchmarks remain pending.
