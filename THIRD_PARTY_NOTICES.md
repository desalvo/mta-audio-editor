# Third-party notices

MTA Audio Editor is licensed under EUPL-1.2. Runtime dependencies retain their own licenses.

| Component | Purpose | Upstream license family |
|---|---|---|
| FastAPI | Web/API framework | MIT |
| Uvicorn | ASGI server | BSD-3-Clause |
| Pydantic | Data validation | MIT |
| python-multipart | Multipart parsing | Apache-2.0 |
| NumPy | Numerical processing / audio alignment | BSD-3-Clause |
| PyTorch | Demucs tensor/inference runtime | BSD-style |
| Demucs | Optional music source separation | MIT |
| FFmpeg | Audio/media processing | LGPL/GPL depending on the concrete distribution build |
| tini | Container init | MIT |
| yt-dlp | YouTube audio-only import | Unlicense / ISC/MIT components as distributed upstream |

The exact license texts and enabled FFmpeg components are determined by the binary packages in the built container. Operators redistributing images should retain the notices supplied by Debian and the upstream packages and verify the resulting FFmpeg licensing configuration.
