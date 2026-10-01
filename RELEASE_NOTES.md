# MTA Audio Editor 0.2.0-9

This release fixes the production container vulnerability gate reached after all quality and source-security jobs passed.

## Container security fix

The Python 3.11 base image supplied `setuptools 79.0.1`, whose vendored packages triggered two HIGH Trivy findings:

- `jaraco.context 5.3.0` / CVE-2026-23949 (fixed in 6.1.0);
- vendored `wheel 0.45.1` / CVE-2026-24049 (fixed in 0.46.2).

The Docker build now upgrades the runtime packaging toolchain to `setuptools==84.0.0` and `wheel==0.48.0` after installing application dependencies. `setuptools 84.0.0` itself vendors fixed `jaraco.context 6.1.0` and `wheel 0.46.3`.

A build-time import smoke test verifies FastAPI/Uvicorn/NumPy and, when stem support is enabled, Torch/Torchaudio before the image is accepted.

## Retained functionality

All 0.2.0-8 functionality is retained, including the current MTA reverse-engineering/analysis features, project documentation, security gates and dynamic CI smoke-test credentials.
