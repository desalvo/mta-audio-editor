# MTA Audio Editor for Android

Native Android client for the MTA Audio Editor server. The app embeds the existing responsive web UI in a hardened WebView and adds Android Storage Access Framework integration for file uploads and export/download destinations.

On first launch the user configures the HTTPS URL of the Docker/Kubernetes backend. Login and project authorization remain server-side. Long-running work (Demucs, rendering, MTA export) runs on the server so the mobile device stays responsive.

## Build

```bash
gradle -p mobile/android :app:assembleDebug
gradle -p mobile/android :app:bundleRelease
```

Release signing is read from `MTA_ANDROID_KEYSTORE_PATH`, `MTA_ANDROID_KEYSTORE_PASSWORD`, `MTA_ANDROID_KEY_ALIAS` and `MTA_ANDROID_KEY_PASSWORD` when present.
