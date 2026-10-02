# MTA Audio Editor for iOS/iPadOS

Native WKWebView client for the MTA Audio Editor Docker/Kubernetes backend. The app stores the chosen backend URL, keeps the authenticated server session in WKWebView, supports Files document-picker uploads, and downloads exports with the same authenticated cookies before presenting the iOS Files save picker or Share sheet.

The heavy DSP, Demucs separation, MTA generation and rendering remain server-side. This avoids bundling Python/PyTorch in the App Store application while preserving the complete editor workflow.

The unsigned archive can be validated in CI with `CODE_SIGNING_ALLOWED=NO`. A distributable/TestFlight IPA requires the normal Apple signing certificate, provisioning profile and App Store Connect credentials.
