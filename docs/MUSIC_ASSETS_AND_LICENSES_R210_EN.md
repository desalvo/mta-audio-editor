# Instruments, singing, transcription and licences — 0.3.0-r210

Review date: 20 October 2026. Version/revision unchanged. This describes actual implementation, not completion of every Vocal Studio requirement or certification of untested hardware. See also the Italian companion and DEVELOPMENT_STATUS.md.

## Free native use and server resources

Native applications and local processing remain entirely free. Server payments are intended exclusively to reimburse CPU, GPU and disk infrastructure operating costs without profit, including requests made by native apps. Subscriptions allocate these server resources; credits cover their permitted overages. Software/model licences are not being sold.

This purpose **does not automatically establish permission** under third-party terms. NonCommercial and hosted/paid-inference restrictions may still apply to hardware reimbursement. Review code, checkpoints, voicebanks, vocoders, dictionaries, dependencies and service conditions separately. Setting the model price to zero does not resolve other restrictions. Primary references: [Creative Commons FAQ](https://creativecommons.org/faq/#does-my-use-violate-the-noncommercial-clause-of-the-licenses) and [NC legal code](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en).

## Optional GM installation

Open **AI Studio → Execution → Studio models and settings**. An administrator or native local user can review notices, install FluidR3 GM, follow actual downloaded bytes, test and uninstall it. Verification/extraction/testing use indeterminate progress where work totals are unavailable. Activation requires real scheduled-note PCM, not just a successful import. Server admin APIs retain authorization; native aliases return 404 on servers.

The same recipe is available through the application's Python interpreter:

```sh
python scripts/install_music_assets.py gm --accept-licenses
python scripts/install_music_assets.py gm --accept-licenses --offline-gm-archive /path/fluid-soundfont_3.1.orig.tar.gz
```

Use the application/runtime interpreter and the service's user and `MTA_DATA_DIR`. Assets live in the data directory. These commands do not reconfigure the running service.

| Component | Source/licence | Integrity |
|---|---|---|
| TinySoundFont | [Upstream](https://github.com/schellingb/TinySoundFont), MIT; commit `853a0a171759f1ddba0de1442133a75912bbeffa` | Header SHA-256 `70d55963c98f60ebb81518eaa1f25d46888d5180eb5f5289fd6b74ffc177d197` |
| FluidR3 GM 3.1 | Frank Wen, MIT; [original Debian archive](https://deb.debian.org/debian/pool/main/f/fluid-soundfont/fluid-soundfont_3.1.orig.tar.gz); original COPYING and README retained | 134,835,922 bytes; `2621acaa1c78e4abdb24bdd163230cc577e61276936d6aa6e3180582142f0343` |
| SF2 bank | 148,398,306 bytes, explicit separate download | `74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0` |
| Alternative FluidSynth | Optional dynamically loaded LGPL-2.1-or-later library | No FluidSynth binary is bundled; preserve its notices and obligations |

The bundled portable C++ engine is the fallback when FluidSynth is absent. MIDI remains editable without a bank. Programs, drum channel, velocity, CC, pitch bend and live controls work. Aftertouch requires FluidSynth or a VSTi. The reverbs differ and do not promise identical sound. Current hardware routing maps stereo master output, not independent per-track hardware buses.

## Real singing with authorized voices

**OddVoices** provides CPU PSOLA/diphone concatenative singing; it is **not neural DiffSinger synthesis**. [Pinned source](https://gitlab.com/oddvoices/oddvoices/-/tree/33a248af8df88edf5166593bf36b7e24e7bc1f94): Apache-2.0 code, explicitly CC0-1.0 vocal recordings. CMUdict 0.7b retains its BSD-style conditions and complete disclaimer. Notices and source provenance are included.

| ID | Voice/register | Actual CPU test |
|---|---|---|
| air | Air Navier, alto | Download, hash verification, compilation, real PCM |
| cicada | Cicada Lumen, baritone | Download, hash verification, compilation, real PCM |
| quake | Quake Chesnokov, bass | Download, hash verification, compilation, real PCM |

Install explicitly from Studio models or run `python scripts/install_music_assets.py air --accept-licenses`, substituting `cicada` or `quake` as needed. No implicit voice download occurs at generation. Original recordings are temporary and removed after compilation or failure. The compiled bank and dictionary are runtime assets: keep them until uninstalling. Large recordings/banks are downloaded separately, not shipped in the cumulative source ZIP.

Workflow: import/transcribe a MIDI melody, optionally create harmony in Vocal Studio, edit the parts in the piano roll, then choose **Render singing from MIDI** in Singers. Select monophonic MIDI source parts, region, voicebank and English syllables or a vocalise. Separate English syllables with `|`, exactly one per note and one vowel nucleus per group. Vocalise mode accepts supported X-SAMPA vowels such as `A`. Formant ratio and articulation speed are configurable.

Italian/French are not declared supported by these banks and are never silently substituted. English is General American, without a guarantee for every word. Notes have independent articulation. Connected melismas, controlled breathing, exposed vibrato/seed, neural expression, timbre conversion and context-aware crossfaded regeneration remain unfinished. Unsupported controls are not simulated.

Execution uses the global queue, cancellation and timeout. Audio and editable MIDI are published together atomically when the project revision is unchanged; otherwise results remain reviewable for explicit import. Closing the dialog does not cancel processing. Publication is idempotent and survives reopening. Downloads and persisted generation metadata retain bank identity, source commit, hashes and settings. Upstream `.voice` parsing is unsafe for arbitrary files: only managed banks compiled from pinned recordings and verified against receipts are accepted. No arbitrary executable/model-bank upload is provided.

## Multi-model reconciliation

**Accurate** mode requires both enabled runtimes: YourMT3 noPS CPU and Basic Pitch ONNX CPU. Missing backends are not silently replaced. Both receive the same source region. Reconciliation uses pitch/onset/offset, one-to-one matching and retained editable original hypotheses. Instrument conflicts, ambiguous unisons and unmatched events remain available. No agreement percentage is presented as calibrated correctness. The reconciliation module supports per-instrument tolerances; primary timing is not quantized.

Source/model checkpoints permit compatible retries to resume completed models without executing them again. From Results, review saved alternatives and import an editable MIDI copy for listening and piano-roll editing. Alternatives persist in the project. Basic Pitch is not a full-mix instrument classifier; combining it with YourMT3 is not evidence of improved accuracy. Comparable real multi-instrument benchmarks remain necessary.

**Maximum accuracy** with stem separation, additional specialist models, rendered comparison and advanced conflict review remains disabled. The system creates no fictitious tracks to reach ten instruments. Existing MIDI/track limits continue to apply.

## Disabled/excluded engines and voicebanks

Known restrictions are distinguished from incomplete rights/backend verification. A licence policy does not install or implement a missing backend.

| Component | Default | Reason and primary source | Activation conditions |
|---|---|---|---|
| Madmom Deep Chroma/CNN-CRF and other upstream weights | Disabled; chord default becomes MTA Chromagram | [BSD code / CC-BY-NC-SA-4.0 models](https://github.com/CPJKU/madmom/blob/main/LICENSE); reimbursement is not automatic permission | Operator verifies permitted noncommercial use or obtains separate authorization; no billing where required |
| Current ChordFormer checkpoint | Disabled | [Configured source](https://github.com/shojha24/ChordFormer-Artificial-Dataset-Benchmarking): queried references did not provide verifiable checkpoint terms | Working source/version, rights and runtime validation |
| Audio-separator/UVR backing-vocal weights | Unreviewed weights disabled; center/side DSP fallback available | [UVR](https://github.com/Anjok07/ultimatevocalremovergui): program licence does not establish every MDX/VR checkpoint's rights | Review exact selected weight release and record permission; this is not a blanket ban on audio-separator |
| DrumSep weights | Disabled pending selected checkpoint review | [Model repository](https://github.com/ZFTurbo/Music-Source-Separation-Training): exact release terms needed | Review specific weights; ONNX code permission alone is insufficient |
| DiffSinger Qixuan | Not distributed; no productive MTA singing backend; disabled | [Terms](https://github.com/yqzhishen/qixuan-diffsinger/blob/main/terms_of_use/Terms_of_Use.zh-CN.md): conditional free hosting, no paid/subscription inference, attribution and complete-bank redistribution requirements | Verified integration and genuinely free access complying with all terms; cost-recovery mode is rejected under these published terms |
| DiffSinger Nishiren | Disabled, not distributed | [Terms](https://github.com/Gardanana/Nishiren-AI-Diffsinger/blob/main/terms-of-service.md): individual commercial approval and other conditions | Actual consent/authorization and compatible backend; zero billing alone is insufficient |
| DiffSinger SPORE | Disabled, not distributed | [Upstream](https://github.com/knoxstation/SPORE): modified NC/ND and additional restrictions | Specific permission/review; no implicit download |
| Other DiffSinger banks, Amphion/SVS, RVC, Seed-VC | Candidates not enabled | Productive adapters and separate voice/weight/vocoder/language review incomplete | Requires functioning backend, rights and actual tests |
| Google MT3, MR-MT3, Transkun, MT3-Infer | Candidates not enabled | Adapters/checkpoints/dependencies and validation incomplete | Integrate and verify before production |
| Future registry engines | Disabled until reviewed | Future component rights cannot be presumed | Explicit operator review and permission source |

Pinned Basic Pitch and YourMT3 declare Apache-2.0; ACE-Step Apache-2.0; Whisper and Demucs MIT. BTC-HCQT explicitly declares [MIT code and weights](https://github.com/marcusfkelley/btc-hcqt), separately from runtime validation. SAM Audio uses the conditional [SAM License](https://github.com/facebookresearch/sam-audio/blob/main/LICENSE), not a blanket NC classification. These engines are **not billing-excluded solely because of those stated licences**. Installation, transitive obligations, additional conditions and hardware compatibility remain separate checks.

## Operator review and accounting

Studio model settings expose disabled, entirely free or permitted hardware-cost recovery modes. An admin/local operator must provide an HTTPS licence/permission reference, reviewed reason, responsibility acknowledgement and, for free-only access, confirmation of the complete free path. The acknowledgement **grants no rights** and is not a replacement for permission. Security controls remain enforced.

Workers retain an immutable licence-decision snapshot. Free-only jobs retain CPU/GPU accounting but have `billable=0`, no charges, no credit debit or paid compute allowance consumption. Reports distinguish them from diagnostic jobs. The token API can execute free inference without subscriptions/credits; temporary result caching is not billed as persistent storage. Authentication, permissions, queueing and security still apply. Operators must not declare a paid web workflow free merely by changing this setting: the required free access path must exist. Free-only Studio results on servers cannot be imported into billed project storage; download the output ZIP instead. Native local projects remain freely saveable. Ordinary quota/billing controls still apply to other authorized jobs.

## ASIO/ROCm acceptance preparation

The following script produces JSON plus SHA-256. Default inventory opens no physical stream, executes no GPU load and changes no service:

```sh
python scripts/verify_music_hardware.py --output hardware.json
# Explicitly inside the engine's ROCm interpreter:
python scripts/verify_music_hardware.py --exercise-rocm --output rocm.json
# Native Windows, installed ASIO driver/PortAudio and exported Audio I/O JSON:
python scripts/verify_music_hardware.py --exercise-audio --audio-settings audio-io.json --require-asio --seconds 10 --output asio.json
```

The audio test sends silence to the selected physical output and checks progress/underruns. It does not certify electrical loopback, input, audible routing or MIDI hardware. The ROCm test runs matrix products timed on one stream; it does not certify AI model compatibility or general process GPU billing. Missing `drm-engine-*` does not prove inactivity or kernel incompatibility. Reports never automatically certify the system.

Real Windows ASIO multichannel loopback/reconnection, independent per-track hardware bus routing, MIDI hardware, new-model inference on Radeon 8060S/ROCm inside LXC, Proxmox-agent counter comparisons and updated-server end-to-end acceptance remain outstanding. ASIO binaries require separate licence/corresponding-source review before distribution. Portable GM and concatenative singing are CPU backends and are never advertised as GPU workloads to justify charges.

## Additional checkpoint review and license admission safeguards (20 October 2026)

None of the four checkpoint families was automatically re-enabled. Madmom pretrained weights are CC BY-NC-SA 4.0; zero pricing does not grant hosted-service permission. ChordFormer has five distinct `s0`–`s4` `.sdict` fold checkpoints in the MTA-configured `shojha24` fork of `mwaseemrandhawa/ChordFormer`, requiring individual provenance/permission review. UVR's official README discusses MIT and attribution for UVR's own trained models, not every third-party mirror or variant; the exact deployed `UVR_MDXNET_KARA_2.onnx` must be tied to a documented release and checksum. The `inagoy/drumsep` repository is MIT, but the MTA ONNX download is from `gridshiftstudio/drumsep-onnx`, pinned SHA-256 `ecb8509383ccd437d84e12c216b002a00a2d4e88601e29f2711ea581f207c92a`, and its model provenance/permission chain remains unverified.

**Implemented:** fail-closed checks before ChordFormer, UVR and DrumSep model downloads and before remote DrumSep inference, plus persistent admin review history with actor and evidence. Operator acknowledgement and an HTTPS URL do not grant third-party rights. Free-only jobs retain usage statistics while billing is excluded under the existing policy. **Not certified:** complete web/native/token billing, subscriptions, reports and invoice acceptance on a production-equivalent server. **Blocked:** automatic reactivation of unverified weights. See `docs/DEVELOPMENT_STATUS.md` for exact tests and limits.
