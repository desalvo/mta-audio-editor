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

## Chordino / NNLS-Chroma bundled runtime
MTA Audio Editor can bundle the NNLS-Chroma/Chordino Vamp plugin in Docker/Kubernetes and native desktop distributions. NNLS-Chroma/Chordino is copyright Matthias Mauch, Chris Cannam and Queen Mary University of London / Centre for Digital Music and is distributed under GNU GPL v2 or later. Upstream source: https://github.com/c4dm/nnls-chroma .

The Linux/macOS builds use the Vamp SDK/simple host where applicable; Vamp SDK components are copyright their respective authors and use their upstream BSD/X11-compatible terms. Windows native packaging may use Sonic Annotator as the Vamp host; Sonic Annotator is distributed under GNU GPL v2 or later. Upstream source: https://github.com/sonic-visualiser/sonic-annotator . The Windows x64 NNLS-Chroma binary is provisioned from a reproducible build of the unmodified upstream plugin source and retains the upstream GPL terms.

## BTC-HCQT / BTC
MTA Audio Editor can download BTC-HCQT on demand for high-accuracy chord recognition.
BTC-HCQT: https://github.com/marcusfkelley/btc-hcqt — MIT, including the published checkpoint.
It is built on BTC-ISMIR19: https://github.com/jayg996/BTC-ISMIR19 — MIT.
The model files are not redistributed in the MTA source ZIP; the user/server downloads them on demand.

## ChordFormer
MTA Audio Editor can download the ChordFormer research implementation and published five-fold checkpoints on demand from:
https://github.com/shojha24/ChordFormer-Artificial-Dataset-Benchmarking
ChordFormer is derived from the MIT-licensed Large-Vocabulary Chord Recognition implementation at:
https://github.com/music-x-lab/ISMIR2019-Large-Vocabulary-Chord-Recognition
The ChordFormer repository/checkpoints are not redistributed in the MTA source ZIP; review upstream attribution/license terms before redistribution.

## Steinberg VST3 SDK and external plugins
The native probe uses standard operating-system module loading and does not
redistribute the Steinberg SDK. Future Steinberg VST3 SDK (version >=3.8)
components, if incorporated, must retain their upstream MIT copyright and
permission notices. Older VST3 SDK releases can have different license terms.
VST3 plugins from third parties are not part of MTA's redistribution rights:
users install and license them separately. Any binary shipped with an installer
requires individual review and inclusion in the binary distribution manifest.

## Pedalboard (optional VST3 offline engine)
Pedalboard is optional and remains independently licensed under GPL-3.0,
including relevant JUCE components. Do not assume EUPL-1.2 compatibility for
all forms of combining binaries: the license and corresponding source obligations
must be reviewed before bundling into native installers.

## Distribution controls
The source static gate in `scripts/license_gate.py` is a preventative check,
not proof of legal compliance. Check resolved Python wheels, OS libraries,
Android/iOS dependencies, model weights, FFmpeg configure flags and codecs,
upstream licenses, source-offer obligations and complete notices for **every**
shipped binary. An unknown license requires review before redistribution.
