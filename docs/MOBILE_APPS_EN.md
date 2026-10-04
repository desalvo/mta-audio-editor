# Android and iOS/iPadOS clients

MTA Audio Editor mobile apps are native clients of the Docker/Kubernetes backend. FFmpeg rendering, waveform processing and MTA generation remain server-side; on iOS/iPadOS, Demucs can also run on-device through Core ML with automatic server fallback.

## Connection

On first launch the app automatically uses its preconfigured service. It **does not ask the user to enter or change a server URL** and **never displays the built-in default address**. From **Server settings** the user can:

- enter a custom HTTPS/HTTP URL;
- view and edit only the custom URL they configured;
- return to the default service without exposing its address.

WebView/WKWebView sessions keep server cookies and authentication.

## Android

- Storage Access Framework for import/export;
- `ACTION_OPEN_DOCUMENT` for uploads;
- `ACTION_CREATE_DOCUMENT` for explicit save destinations;
- Sharesheet for sharing;
- authenticated downloads using WebView cookies.

## iOS/iPadOS

- `UIDocumentPickerViewController` for import/export;
- Files/iCloud Drive integration;
- Share Sheet;
- protected downloads using cookies from `WKHTTPCookieStore`.

## Long-running jobs

Demucs and rendering continue on the server. The client keeps the display awake during active jobs when possible; if iOS/Android suspends WebView polling, the server job continues and state is restored when the app resumes.

## Build and signing

Android produces a debug APK and release AAB; iOS produces an unsigned `.xcarchive.zip` and, when signing secrets are available, IPA/TestFlight artifacts. Signing variables belong in CI secrets and must never be embedded in source code.

## Offline mode

The mobile apps do not bundle full Python/PyTorch/FFmpeg runtimes; stem separation and master rendering require a reachable server.

### Configurable stem count
Stem separation exposes **Auto / 2 / 4 / 6 / 8**. Auto is the default. 2 uses vocals/accompaniment, 4 the standard profile, 6 the extended Demucs profile; 8 requires a backend configured with an 8-stem model. The current iPhone and iPad build delegates Demucs to the server, so the same setting is available on both devices without bundling PyTorch in the app.


## On-device Demucs on iPhone/iPad (0.2.0-97)

The iOS/iPadOS client can now run stem separation locally through Core ML. The mobile workflow exposes **Auto / Local / Server** execution. Auto prefers an installed local model and falls back to server-side Demucs when the requested model is unavailable or the local device constraints are exceeded. Core ML models are provisioned as `demucs-2.mlmodel`, `demucs-4.mlmodel`, `demucs-6.mlmodel`, or `demucs-8.mlmodel` from the configured backend and are compiled/cached in the app's Application Support directory for later offline use.

The local runtime decodes the selected audio on-device, converts it to stereo 44.1 kHz Float32 PCM, processes fixed-size overlapping chunks through Core ML using all available compute units (CPU/GPU/Neural Engine where Core ML supports them), overlap-adds the results, writes WAV stems, and uploads the resulting tracks into the current project. The current local safety limit is **12 minutes per source file**; longer material falls back to the server in Auto mode. On iPhone, Auto is intentionally more conservative than on iPad because of memory/thermal constraints.

Server administrators can expose compatible Core ML Demucs models by mounting a directory and setting `MTA_DEMUCS_COREML_MODEL_DIR`. The optional `scripts/export_demucs_coreml.py` utility documents the model contract expected by the app. Model conversion is a release-engineering step and must be validated for each Demucs architecture before publishing a model.

## Periodic Demucs model updates
On iPhone/iPad and Android, **Update on Wi-Fi only** is enabled by default. Every six hours and at startup, the client checks the server catalogue and downloads only models whose SHA-256 changed. Disabling the switch permits cellular downloads. The Docker/Kubernetes server periodically refreshes its local mobile-model repository from a configurable HTTPS manifest.
