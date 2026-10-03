# Android and iOS/iPadOS clients

MTA Audio Editor mobile apps are native clients of the Docker/Kubernetes backend. FFmpeg rendering, Demucs, waveform processing and MTA generation remain server-side.

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
