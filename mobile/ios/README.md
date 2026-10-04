# MTA Audio Editor for iOS/iPadOS

Native WKWebView client for the MTA Audio Editor Docker/Kubernetes backend. The app stores the chosen backend URL, keeps the authenticated server session in WKWebView, supports Files document-picker uploads, and downloads exports with the same authenticated cookies before presenting the iOS Files save picker or Share sheet.

FFmpeg rendering and MTA generation remain server-side, while Demucs stem separation can now run either **on-device through Core ML** or on the server. Stem count is model-driven: Auto plus every compatible count advertised by the server or installed locally (for example 2, 4, 6, 8, 10, 12, 16 or more). Auto prefers an installed local Core ML model when the device and requested profile are suitable, otherwise it falls back to server-side Demucs. The same controls are available on iPhone and iPad, with more conservative Auto recommendations on iPhone.

The unsigned archive can be validated in CI with `CODE_SIGNING_ALLOWED=NO`. A distributable/TestFlight IPA requires the normal Apple signing certificate, provisioning profile and App Store Connect credentials.


## On-device Demucs on iPhone/iPad (0.2.0-97)

The iOS/iPadOS client can now run stem separation locally through Core ML. The mobile workflow exposes **Auto / Local / Server** execution. Auto prefers an installed local model and falls back to server-side Demucs when the requested model is unavailable or the local device constraints are exceeded. Core ML models are provisioned as `demucs-2.mlmodel`, `demucs-4.mlmodel`, `demucs-6.mlmodel`, or `demucs-8.mlmodel` from the configured backend and are compiled/cached in the app's Application Support directory for later offline use.

The local runtime decodes the selected audio on-device, converts it to stereo 44.1 kHz Float32 PCM, processes fixed-size overlapping chunks through Core ML using all available compute units (CPU/GPU/Neural Engine where Core ML supports them), overlap-adds the results, writes WAV stems, and uploads the resulting tracks into the current project. The current local safety limit is **12 minutes per source file**; longer material falls back to the server in Auto mode. On iPhone, Auto is intentionally more conservative than on iPad because of memory/thermal constraints.

Server administrators can expose compatible Core ML Demucs models by mounting a directory and setting `MTA_DEMUCS_COREML_MODEL_DIR`. The optional `scripts/export_demucs_coreml.py` utility documents the model contract expected by the app. Model conversion is a release-engineering step and must be validated for each Demucs architecture before publishing a model.


## Model-driven extended stem separation

MTA Audio Editor no longer hard-codes a 2/4/6/8 list. The server and mobile clients discover the stem counts actually published by the model catalogue/manifest: 2, 4, 6, 8, 10, 12, 16, and larger values whenever a compatible model exists. The current safety ceiling is 64 stems per model. Multitrack DAW projects are not constrained by the stem count; MTA8/MTA16 limits are enforced only at export time. Additional server profiles are configured through `MTA_DEMUCS_MODEL_REGISTRY` or `MTA_DEMUCS_MODEL_REGISTRY_FILE`, declaring `model`, `stem_count`, `stem_labels`, and optionally `engine`/`display_name`.

## Local model management

The iOS/iPadOS client uses the server model catalogue by model ID. A missing Core ML model is downloaded automatically when that model is requested for local splitting. Installed models are periodically checked for newer SHA-256 fingerprints (Wi-Fi only by default). The native options menu can force-update or delete individual local models; a deleted model is downloaded again on demand.
