# MTA Audio Editor for Android

Native Android client for the MTA Audio Editor server. The app embeds the existing responsive web UI in a hardened WebView and adds Android Storage Access Framework integration for file uploads and export/download destinations.

On first launch the user configures the HTTPS URL of the Docker/Kubernetes backend. Login and project authorization remain server-side. Long-running work (Demucs, rendering, MTA export) runs on the server so the mobile device stays responsive.

## Build

```bash
gradle -p mobile/android :app:assembleDebug
gradle -p mobile/android :app:bundleRelease
```

Release signing is read from `MTA_ANDROID_KEYSTORE_PATH`, `MTA_ANDROID_KEYSTORE_PASSWORD`, `MTA_ANDROID_KEY_ALIAS` and `MTA_ANDROID_KEY_PASSWORD` when present.


## Model-driven extended stem separation

MTA Audio Editor no longer hard-codes a 2/4/6/8 list. The server and mobile clients discover the stem counts actually published by the model catalogue/manifest: 2, 4, 6, 8, 10, 12, 16, and larger values whenever a compatible model exists. The current safety ceiling is 64 stems per model. Multitrack DAW projects are not constrained by the stem count; MTA8/MTA16 limits are enforced only at export time. Additional server profiles are configured through `MTA_DEMUCS_MODEL_REGISTRY` or `MTA_DEMUCS_MODEL_REGISTRY_FILE`, declaring `model`, `stem_count`, `stem_labels`, and optionally `engine`/`display_name`.

## Local model management

The Android client uses the server ONNX catalogue by model ID. Models selected for splitting are prefetched on demand, and installed models are refreshed periodically according to the Wi-Fi-only preference. **Gestione modelli Demucs** in the native options can force-update/download or delete individual local models.
