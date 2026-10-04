# Mobile applications / Applicazioni mobili

- Italiano: [`MOBILE_APPS_IT.md`](MOBILE_APPS_IT.md)
- English: [`MOBILE_APPS_EN.md`](MOBILE_APPS_EN.md)


## On-device Demucs on iPhone/iPad (0.2.0-97)

The iOS/iPadOS client can now run stem separation locally through Core ML. The mobile workflow exposes **Auto / Local / Server** execution. Auto prefers an installed local model and falls back to server-side Demucs when the requested model is unavailable or the local device constraints are exceeded. Core ML models are provisioned as `demucs-2.mlmodel`, `demucs-4.mlmodel`, `demucs-6.mlmodel`, or `demucs-8.mlmodel` from the configured backend and are compiled/cached in the app's Application Support directory for later offline use.

The local runtime decodes the selected audio on-device, converts it to stereo 44.1 kHz Float32 PCM, processes fixed-size overlapping chunks through Core ML using all available compute units (CPU/GPU/Neural Engine where Core ML supports them), overlap-adds the results, writes WAV stems, and uploads the resulting tracks into the current project. The current local safety limit is **12 minutes per source file**; longer material falls back to the server in Auto mode. On iPhone, Auto is intentionally more conservative than on iPad because of memory/thermal constraints.

Server administrators can expose compatible Core ML Demucs models by mounting a directory and setting `MTA_DEMUCS_COREML_MODEL_DIR`. The optional `scripts/export_demucs_coreml.py` utility documents the model contract expected by the app. Model conversion is a release-engineering step and must be validated for each Demucs architecture before publishing a model.


## Model-driven extended stem separation

MTA Audio Editor no longer hard-codes a 2/4/6/8 list. The server and mobile clients discover the stem counts actually published by the model catalogue/manifest: 2, 4, 6, 8, 10, 12, 16, and larger values whenever a compatible model exists. The current safety ceiling is 64 stems per model. Multitrack DAW projects are not constrained by the stem count; MTA8/MTA16 limits are enforced only at export time. Additional server profiles are configured through `MTA_DEMUCS_MODEL_REGISTRY` or `MTA_DEMUCS_MODEL_REGISTRY_FILE`, declaring `model`, `stem_count`, `stem_labels`, and optionally `engine`/`display_name`.
