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


## Private X.Org display build source

The source-only archive `native/server_display/vendor/xorg-server-21.1.24.tar.xz` is an unmodified upstream X.Org release, SHA-256 `1a4eb36ca65cc3b1b936566d677a9786e13c11cd5806e951ac55f3f5ce3984af`, originally retrieved from https://xorg.freedesktop.org/releases/individual/xserver/xorg-server-21.1.24.tar.xz. It is retained to remove the external DNS dependency during RPM/DEB builds. The complete upstream licence notices remain in the archive and in the adjacent `XSERVER-COPYING`; compiled server packages carry those notices. No precompiled X server or third-party VST plugin is included in this source archive.


## miniaudio

The C++ audio device transport uses miniaudio 0.11.23, copyright David Reid, under its MIT No Attribution option. The unmodified header and full upstream licensing text are retained at `native/third_party/miniaudio/miniaudio.h`; the adjacent README records its version and SHA-256. Docker's isolated audio-core build copies this directory alongside the core sources.

## Optional open-source VST3 catalog (r210, 2026-10-19)

MTA ships a reviewed catalog, license texts and source-build recipes for MVerb,
Dragonfly Reverb, CHOW Tape Model and Surge XT, not their binaries. Installations
are opt-in and separate from MTA/project files. Full main-project license texts
are in `app/optional_plugin_licenses/`; pinned revisions, SHA-256 digests,
submodule/source retention and redistribution considerations are documented in
`docs/OPTIONAL_VST3_CATALOG_IT.md` and `docs/OPTIONAL_VST3_CATALOG_EN.md`.
MVerb is GPLv3-or-later; the other projects declare GPLv3. DPF VST3 implementation
uses ISC and requires attribution. JUCE, bundled libraries and content retain
individual terms. These recipe/notice additions do not authorize redistribution
of unrelated VST2 binaries or omit corresponding-source obligations.

## Optional AI Studio / MIDI additions (r210, 20 October 2026)

The source archive contains MTA adapter code and fixed optional installation instructions, **not** third-party model weights, Python environments, FluidSynth binaries or voicebanks.

- Basic Pitch 0.4.0: Spotify, Apache-2.0; upstream code and included ONNX model. https://github.com/spotify/basic-pitch/blob/main/LICENSE . Reviewed model SHA-256: `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`.
- ONNX Runtime: Microsoft, MIT. https://github.com/microsoft/onnxruntime/blob/main/LICENSE . The Studio adapter disables telemetry before initialization and through the runtime API. Preserve the wheel's dependency notices for any separately distributed runtime.
- FluidSynth: LGPL-2.1-or-later, dynamically loaded optional library. https://github.com/FluidSynth/fluidsynth/blob/master/LICENSE . FluidR3 GM soundbank has a separate MIT license; Debian packaging uses separate terms: https://sources.debian.org/src/fluid-soundfont/3.1-6/debian/copyright . Bank checksum/size and operational restrictions are recorded in the Studio implementation documents.
- NumPy, SciPy, librosa, soundfile, resampy, pretty-midi, ONNX Runtime and transitive dependencies retain their respective distribution notices in the separately installed environment. This notice is not a complete binary-runtime license audit or dependency lock.
- DiffSinger, Amphion, RVC, Seed-VC, MT3, MR-MT3, Transkun and MT3-Infer are **not distributed or enabled** by appearing in the candidate catalog. Code, checkpoint, voicebank, dataset and dependency rights must be checked separately. In particular, noncommercial vocoder/voicebank releases are not authorized by this project for billed services.

Current review and limitations: `docs/STUDIO_WORKFLOWS_R210.md` and `docs/STUDIO_WORKFLOWS_R210_EN.md`. Recheck official sources and all separately distributed runtime contents when updating versions. Process isolation does not automatically resolve copyleft obligations.


## Portable GM and optional singing (r210, 20 October 2026)

- TinySoundFont: MIT; unchanged header at `native/third_party/tinysoundfont/tsf.h`, pinned upstream commit `853a0a171759f1ddba0de1442133a75912bbeffa`; full MIT notice adjacent. https://github.com/schellingb/TinySoundFont .
- FluidR3 GM 3.1: Frank Wen, MIT. Optional source archive SHA-256 `2621acaa1c78e4abdb24bdd163230cc577e61276936d6aa6e3180582142f0343`; soundbank SHA-256 `74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0`. Installer retains original COPYING and README. No bank samples are shipped in this source ZIP.
- OddVoices: Nathan Ho, Apache-2.0 engine; Air Navier, Cicada Lumen and Quake Chesnokov vocal recordings are explicitly CC0-1.0. Source pinned at `33a248af8df88edf5166593bf36b7e24e7bc1f94`, with original license texts and original-file digests in `native/third_party/oddvoices/`. Recording download hashes are in `app/studio_assets/oddvoices_assets.json`. The optional installer compiles recordings into a managed bank; no recordings or compiled banks are distributed in this source archive.
- CMUdict 0.7b: Carnegie Mellon University, BSD-style two-clause terms. The complete copyright and disclaimer remain in the pinned downloaded dictionary and in `app/studio_assets/CMUDICT-LICENSE.txt`.
- OddVoices changes, 20 October 2026: UTF-8 filesystem path opening for Windows in g2p.cpp and liboddvoices.cpp; inline missing Synth::isErrored definition; optional audio_source argument in CorpusAnalyzer to stream bounded windows. Original digests are provenance, not hashes of these patched files. All other vendored source files are retained unchanged.
- YourMT3 noPS runtime is operator-installed under its pinned author's Apache-2.0 declaration; it is not enabled merely by appearing in the model catalog. See YOURMT3_RUNTIME_R210 documentation and dependency notices.

Local native software use is free. Server payment is intended only to reimburse CPU, GPU and storage infrastructure costs, without profit. This does not itself remove noncommercial, hosted-inference, subscription, redistribution, voice-consent or other license restrictions. Default restrictions and manual operator review are documented in MUSIC_ASSETS_AND_LICENSES_R210. Process boundaries do not waive license obligations.
