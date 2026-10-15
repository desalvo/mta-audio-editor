# AI Source Audio Contract / Contratto audio sorgente

EN: Revision 184 stages **verified WAV inputs** from the authenticated project into a temporary private worker directory, passing relative `source_audio` entries in the request JSON. The original project audio is not modified. Missing sources, non-WAV tracks, symbolic links and oversized source sets fail closed. The worker runs separately from the real-time audio callback. This does not provide an ACE-Step adapter, model weights, automatic stems, or end-to-end production validation.

IT: La revisione 184 copia gli **ingressi WAV verificati** del progetto autenticato in una directory temporanea privata del worker e trasmette le voci relative `source_audio` nel JSON di richiesta. I file originali non vengono modificati. Sorgenti mancanti, tracce non WAV, link simbolici e gruppi audio eccessivi sono rifiutati. Il worker opera separatamente dal callback realtime. Non è ancora presente un adattatore ACE-Step, non sono inclusi pesi dei modelli e non sono validate generazione reale e importazione stem.

Protocol example / Esempio:

```json
{"source_audio": [{"track_id": "track1", "filename": "inputs/000.wav", "channels": 2, "sample_rate": 44100, "frames": 441000}]}
```

The worker must accept `--request <request.json> --output <preview.wav>` and write a valid PCM WAV. A real model-specific adapter and end-to-end musical fidelity tests remain required.
