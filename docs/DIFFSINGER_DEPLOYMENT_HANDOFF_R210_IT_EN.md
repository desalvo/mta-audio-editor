**Aggiornamento r210:** è disponibile anche il percorso OpenUtau ONNX verificato con Qixuan 2.7.0. Il seguito descrive il percorso nativo `.ckpt`; per ONNX, pacchetto completo e condizioni vedere [guida aggiornata](R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md).

# DiffSinger deployment handoff / Passaggio al collaudo DiffSinger (0.3.0-r210)

## Italiano

### Verifiche realizzate
- Bridge DiffSinger acustico, conversione `.ds`, contratto dei WAV, controllo SHA-256 e ammissione licenze: mantenuti.
- `scripts/check_diffsinger_ready.py`: controllo **in sola lettura** di runtime ufficiale, esperimento, asset acustico, vocoder, relativi SHA-256 e policy AI; non scarica, non installa, non modifica lo stato di licenza.
- `python scripts/check_diffsinger_ready.py --json` termina con codice 2 se non è pronto, 0 se sono presenti le condizioni preliminari. `real_audio_validated` rimane sempre `false`: la verifica preliminare non è una prova di qualità o compatibilità GPU.

### Intervento del gestore necessario per la certificazione finale
1. Predisporre sul server di test un ambiente OpenVPI DiffSinger compatibile, completo di modello acustico, voicebank e vocoder **con diritti verificati per l'utilizzo previsto**. Conservare provenienza, URL della licenza e SHA-256 di ciascun artefatto.
2. Impostare (solo sul server, mai nelle richieste degli utenti): `MTA_DIFFSINGER_ROOT`, `MTA_DIFFSINGER_EXPERIMENT`, `MTA_DIFFSINGER_PYTHON`, `MTA_DIFFSINGER_PYTHON_SHA256`, `MTA_NEURAL_SINGER_CHECKPOINT`, `MTA_NEURAL_SINGER_SHA256`, `MTA_DIFFSINGER_VOCODER`, `MTA_DIFFSINGER_VOCODER_SHA256`, `MTA_NEURAL_SINGER_POLICY_MODEL`.
3. Eseguire `python scripts/check_diffsinger_ready.py --json` e conservare il risultato senza esporre percorsi o informazioni personali in ambienti pubblici.
4. Eseguire una vera generazione di canto da MIDI con fonemi espliciti conformi al dizionario della voicebank, ascoltare i WAV, misurare durata, intonazione, qualità e uso CPU/GPU; verificare la persistenza nel progetto MTA.
5. Completare i test web, native e ROCm e la regressione completa prima di dichiarare la macroarea conclusa.

### Limitazioni
Non sono incluse voicebank neurali, vocoder, fonemizzatori IT/FR né modelli commercialmente autorizzati. L'inferenza reale e la conversione timbrica rimangono da concludere. La sola presenza di un checkpoint non prova i diritti d'uso. La modalità `cost_recovery` non rende utilizzabili pesi NC.

## English

### Implemented checks
- Existing DiffSinger acoustic CLI bridge, `.ds` conversion, WAV checks, pinned SHA-256 verification and license admission are preserved.
- `scripts/check_diffsinger_ready.py` is a **read-only** preflight covering runtime, experiment, acoustic checkpoint, vocoder, SHA-256 pins and AI policy. It does not download weights or grant any rights.
- `python scripts/check_diffsinger_ready.py --json` exits 2 when blocked, 0 when preconditions are met. `real_audio_validated` is always `false` until a separately documented genuine inference test is performed.

### Operator intervention needed for final validation
1. Install the official DiffSinger runtime with licensed acoustic model, voicebank and vocoder on the staging machine. Preserve provenance and SHA-256 values.
2. Supply the environment settings listed above and an approved policy model identity.
3. Run the preflight command and archive its report.
4. Generate actual singing audio with bank-compatible phonemes and validate listening quality, pitch, timing, CPU/GPU accounting, persistence and import.
5. Test browser, native and AMD ROCm paths and run the complete regression suite before signing off.

### Outstanding
Actual neural inference, IT/FR G2P, timbral conversion, hardware validation and complete end-to-end production tests are not certified. No new neural weights are included in this source ZIP.
