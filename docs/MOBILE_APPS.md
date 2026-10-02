# Android and iOS/iPadOS clients

MTA Audio Editor ships native mobile clients in `mobile/android` and `mobile/ios`. They deliberately use the existing Docker/Kubernetes server for project storage, Demucs stem separation, FFmpeg rendering, waveform processing and MTA generation. This keeps the mobile packages small and avoids shipping Python/PyTorch runtimes that are unsuitable for normal App Store distribution.

## Connection model

On first launch, the app asks for the MTA Audio Editor server URL. HTTPS is recommended for every non-local deployment. Authentication, roles and project access are handled by the server exactly as in the normal web interface. WebView/WKWebView session cookies are also passed to native file downloads, so exported files remain protected by the same authenticated session.

The server URL can be changed later from the native app menu/navigation bar.

## Native filesystem integration

Android uses the Storage Access Framework:

- `ACTION_OPEN_DOCUMENT` for project/audio uploads;
- `ACTION_CREATE_DOCUMENT` for explicit export destinations;
- Android Sharesheet for direct sharing of generated files.

The app downloads protected files itself with the WebView authentication cookie before writing to the selected document URI.

iOS/iPadOS uses `UIDocumentPickerViewController` for imports and exports. Protected downloads are performed with cookies copied from `WKHTTPCookieStore`; the result can then be saved to Files/iCloud Drive or sent through the system Share sheet.

The responsive web UI detects `window.MtaMobile` and uses a server-side export job for MTA/WAV/MP3/FLAC. This avoids Blob downloads inside mobile WebViews and lets the native shell choose the final filesystem destination.

## Long-running work

Demucs and rendering continue on the server and expose progress through the existing job APIs. While a long-running job is active, the mobile bridge requests that the device keep the display awake. The UI can be backgrounded, but iOS/Android may suspend WebView polling; the server-side job itself continues and its state is available again when the app resumes.

## Android build/signing

CI always builds a debug APK and a release AAB. For a Play-ready signed AAB configure these GitHub repository secrets:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

The keystore secret is the base64 representation of the binary keystore.

## iOS build/signing/TestFlight

CI always builds an unsigned `.xcarchive.zip` to validate the iOS application. To generate a signed IPA configure:

- `IOS_CERTIFICATE_P12_BASE64`
- `IOS_CERTIFICATE_PASSWORD`
- `IOS_PROVISIONING_PROFILE_BASE64`
- `IOS_TEAM_ID`

The provisioning profile must contain bundle identifier `com.desalvo.mtaaudioeditor.mobile`.

For automatic TestFlight upload on a Git tag also configure:

- `APPSTORE_CONNECT_KEY_ID`
- `APPSTORE_CONNECT_ISSUER_ID`
- `APPSTORE_CONNECT_PRIVATE_KEY`

The App Store Connect private key secret contains the complete `.p8` contents.

## Offline mode

The initial Android/iOS applications are native clients, not copies of the desktop single-user runtime. Audio separation and master rendering therefore require a reachable MTA Audio Editor server. This is intentional: the current desktop stack includes Python, FFmpeg and PyTorch/Demucs, which should not be embedded directly in an App Store application. Local-device inference can later be introduced behind a mobile processing backend (for example Core ML/ONNX) without changing project format or the mobile UI contract.
