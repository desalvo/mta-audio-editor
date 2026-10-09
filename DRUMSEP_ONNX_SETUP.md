# DrumSep ONNX / DrumSep ONNX

DrumSep separates Kick, Snare, Cymbals and Toms from a pre-separated drums stem (Demucs stage). Other percussion, such as congas and bongos, must be extracted with SAM Audio instead.

Il modello è opzionale; il pulsante **Scarica modello DrumSep** nelle opzioni di separazione salva il modello in `MTA_DRUMSEP_MODEL_DIR` o, in mancanza, nella cartella `.cache/drumsep-models` dell’archivio dati.

Requires Python `onnxruntime`, `scipy`, `numpy`, and `soundfile` in the application runtime. The downloaded model is SHA-256 verified before atomically replacing the existing model. CPU inference is the default.

Model: https://huggingface.co/gridshiftstudio/drumsep-onnx (MIT). Original model: https://github.com/inagoy/drumsep.

**Limite / Limitation:** ONNX conversion uses external STFT. Validate stems against reference ONNX implementation before considering audio quality production-certified.
