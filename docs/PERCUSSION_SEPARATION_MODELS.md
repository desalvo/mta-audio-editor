# Percussion separation models — reviewed candidate register

Review date: **2026-11-03**. Machine-readable register: `app/percussion_candidates.json`. Runtime contract: `app/percussion_adapters.py`. This is a candidate and provenance register, not an approval of model quality or of unreviewed weights. No candidate is downloaded automatically and no trained weights are redistributed in the MTA package.

## Implemented baseline

**MVSep Mega 53 v1.0.21** is the only executable adapter in this register. It reuses the existing MTA Mega 53 adapter and its original pinned SHA-256:

`c62820893bbf86d4e734f966bd142d9157cfc8bb8e79e9d8f9ea553f3ff3519f`

The author explicitly permits MIT use of the 53-stem weights in [issue 245](https://github.com/ZFTurbo/Music-Source-Separation-Training/issues/245). The statement does not warrant training-data rights. MTA keeps the existing independent policy checks before/after inference; disabling the model remains effective. [The release](https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/tag/v1.0.21) recommends at least 16 GB VRAM and explains that estimated stems overlap. RAM, runtime and ROCm behavior have not been measured in this environment.

Configure the separately installed official runtime, matching YAML and exact weights using `MTA_MEGA53_ROOT`, `MTA_MEGA53_CONFIG`, `MTA_MEGA53_CHECKPOINT` and, if necessary, `MTA_MEGA53_PYTHON`. There is no download fallback. `verify_installation()` hashes the installed checkpoint, YAML and upstream entry point before explicit use. A configured path does not count as a verified installation. The registered server execution additionally retains its existing interpreter, ownership, rights, process and metering checks; the local adapter does not certify an arbitrary upstream checkout or its dependencies.

The benchmark profile asks Mega 53 for its native `percussion` class and, by default, its independent `kick` class. Setting `include_kick=false` requests only percussion. Clap and timpani classification is configurable in the request schema, but independently including either is currently **incompatible** with this adapter, rather than silently substituting a different class. Default: both excluded. A broad native class is an estimate; complete recovery of congas, shakers or other accessories must be established by the benchmark and human listening.

For kick inclusion the adapter writes an explicitly declared additive composite and retains the component WAVs. It never subtracts kit estimates or silently normalizes audio. Overlap, introduced clipping, nonfinite samples, altered duration or lost stereo channels cause a failed/invalid result. No perfect reconstruction is claimed. If fixed-rate inference returns 44.1 kHz stereo for a 48 kHz or mono input, a recorded polyphase conversion restores the original format and exact frame count (maximum two-frame rounding tolerance); untouched raw component WAVs remain available. Mono output from stereo input is rejected.

Each prepared request records the exact checkpoint revision/hash, adapter version, pipeline source SHA-256, category policy, source mode and a deterministic profile hash. The original mix can be selected explicitly and compared in a separate run with the DRUMS source; the adapter never silently switches or combines the two inputs.

## Candidates and actual disposition

| Candidate | Verified source information | Current disposition |
| --- | --- | --- |
| Mega 53 v1.0.21 | Author MIT statement; exact existing checkpoint pin; official MSST implementation | Adapter implemented; requires installed verified assets and current policy. No new real-model inference here. |
| BS-RoFormer Percussion v2 — Xlance | [Public registry](https://huggingface.co/noblebarkrr/mvsepless_resources/blob/main/models.json) lists `bs_perc2_xlancer.ckpt`, percussion/other | Disabled: mirror listing does not establish a first-party weight license or SHA-256. Priority specialist candidate after provenance is supplied. |
| BS-RoFormer Percussion v1 — Xlance | Same registry, `bs_perc_xlancer.ckpt` | Disabled for the same exact-weight permission and identity gaps. |
| Mel-Band RoFormer Percussion — yolkispalkis | Same registry, experimental percussion/other model | Disabled: original provenance, permissions and checkpoint identity unverified. |
| AudioSep-Hive | [Publisher model card](https://huggingface.co/AlayaLab/AudioSep-hive) declares Apache-2.0; principal checkpoint SHA below | Research candidate; no executable adapter. CLAP asset, runtime dependency rights and fidelity/stereo behavior still require review. |
| FlowSep-Hive | [Publisher card](https://huggingface.co/AlayaLab/FlowSep-hive) declares Apache-2.0; principal checkpoint SHA below | Research candidate; no executable adapter. VAE/runtime review, generative fidelity and actual benchmark remain open. |
| CLAPSep | [Official code](https://github.com/Aisaka0v0/CLAPSep) MIT with third-party notices; author-linked HF checkpoint | Disabled: exact weight and encoder permission review not completed, adapter not implemented. |
| Banquet | [Official code](https://github.com/kwatcharasupat/query-bandit) MIT; [author weight record](https://zenodo.org/records/13694558), recommended `ev-pre-aug.ckpt` | Disabled: retrieved weight record exposed MD5 but no usable license value; SHA-256 and all encoder permissions unresolved. Audio-reference query integration remains open. |
| Separate-and-Detect | [Official repository](https://github.com/ddman1101/Separate-and-detect) MIT; latent-diffusion generation of five kit classes | Incompatible as faithful accessory-percussion extraction. Possible kit-support research only; no inference or naive subtraction enabled. |
| DrumSep / MDX23C derivatives | [Original DrumSep](https://github.com/inagoy/drumsep) and [Intel conversion](https://huggingface.co/Intel/drumsep_mdx23c_jarredou_openvino) are distinct sources; Intel labels its conversion CC-BY-NC-SA-4.0 | Upstream weight grant remains unresolved; conversion license is not a general commercial permission. Existing rights block retained. |
| MTA Percussion Separator | Future model with purpose-built classes and licensed data | Roadmap only; no training initiated before comparable existing-model evidence. |

## Retrieved checkpoint identities

These hashes were read from the publisher/author-linked file metadata, without downloading or executing the large checkpoint files. A principal checkpoint pin alone does not authorize the complete model runtime or its auxiliary assets.

| Candidate | File/revision shown by publisher | SHA-256 |
| --- | --- | --- |
| AudioSep-Hive | `audiosep_hive.ckpt`, upload `14f91a1` | `a13fff5fa4ece1a8bc13e42e1c7b8d90e21603075302ca89e4339c9471973300` |
| AudioSep CLAP dependency | `music_speech_audioset_epoch_15_esc_89.98.pt`, upload `438413b` | `51c68f12f9d7ea25fdaaccf741ec7f81e93ee594455410f3bca4f47f88d8e006` |
| FlowSep-Hive | `flowsep_hive.ckpt`, upload `f02e798` | `3b7b5379592251dc655757a7dbac109346cbc6c8763dd73efd19326fe6c39fdd` |
| CLAPSep | `model/best_model.ckpt`, upload `fbe31d2` | `6fcc8dbcd7174af86266cf16b4105eced0802352762f81dbfefdce29af3dba04` |

Primary metadata URLs: [AudioSep weights](https://huggingface.co/AlayaLab/AudioSep-hive/blob/main/audiosep_hive.ckpt), [CLAP dependency](https://huggingface.co/AlayaLab/AudioSep-hive/blob/main/music_speech_audioset_epoch_15_esc_89.98.pt), [FlowSep weights](https://huggingface.co/AlayaLab/FlowSep-hive/blob/main/flowsep_hive.ckpt), [CLAPSep weights](https://huggingface.co/spaces/AisakaMikoto/CLAPSep/blob/main/model/best_model.ckpt). The [Hive project](https://github.com/AlayaLab/Hive) releases dataset mixing metadata and says original source audio must be obtained under its own terms. Its top-level code license does not independently settle every upstream audio or auxiliary weight grant.

## Dataset suitability checked

- [FreePats World percussion](https://freepats.zenvoid.org/Percussion/world-and-rare-percussion.html), version 2020-09-05: CC0-1.0, real isolated recorded instrument samples; appropriate for constructing attributed/versioned controlled mixtures. These rendered mixtures must still be labelled synthetic mixtures, not recordings of a real ensemble. No samples were downloaded in this adapter task.
- [WaivOps WRLD-LP](https://github.com/WaivOps/WaivOps-WRLD-LP): CC BY 4.0 mixed world-percussion rhythms, 24-bit/44.1 kHz. Useful for perceptual tests, not exact per-instrument bleed ground truth without additional isolated recordings.
- [Expanded Groove MIDI Dataset](https://magenta.withgoogle.com/datasets/e-gmd): CC BY 4.0, paired MIDI and recorded electronic kit audio, 90 GB audio archive. MIDI annotations do not supply isolated audio stems. Retain the original sequence-level train/validation/test split across all kit variants; the documented audio/MIDI alignment is within 2 ms, not sample-exact per-instrument truth.

No third-party dataset audio is included by this adapter work.

## Software evidence and remaining acceptance

`tests/test_r210_percussion_adapters.py` exercises catalog/activation, exact-profile binding, fail-closed rights and unowned dispatch, optional kick, declared source choice, PCM preservation, deterministic format conversion, cancellation, and invalid/stale output rejection. These use synthetic WAVs and stubbed registered inference. They do **not** establish neural separation quality or real model installation.

The developer command `python -m app.percussion_benchmark_cli` provides `prepare`, `catalog`, `list`, `show`, `reports` and `export`. An explicit absolute local data root can be selected; every operation then enters that authority's service-admission gate and is blocked during drain. It has no unowned inference or approval command; benchmark execution and approval use the authenticated application APIs. Export creates a new ZIP and refuses to overwrite an existing file. `tests/test_r210_percussion_benchmark_cli.py` checks these boundaries, including a real drained admission journal and rejection before benchmark effects.

Only a real completed inference establishes technical operation for an exact model installation. Automatic corpus results and controlled listening are separate later stages. All profiles remain **In attesa di validazione umana** until the user approves the exact model, pipeline and configuration after guided listening. No professional-quality approval is inferred from contract tests or a license declaration.
