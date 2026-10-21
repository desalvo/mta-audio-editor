# YourMT3 and native audio devices — r210

Version remains 0.3.0-r210. This integration does not complete the full AI Studio specifications.

## CPU multi-instrument transcription

The YourMT3 noPS adapter uses the original author's [mimbres/YourMT3 Space](https://huggingface.co/spaces/mimbres/YourMT3/tree/5e66c1ea173a8186e0d20432b841d3180cc015b5), pinned commit `5e66c1ea173a8186e0d20432b841d3180cc015b5`. The source manifest records each file's digest and size. Opening a project never downloads this model.

Explicit Linux CPU installation (Windows/macOS are not supported by this recipe yet), from a project checkout using Python 3.11/3.12:

```sh
python3.12 scripts/install_studio_yourmt3.py \
  --runtime /opt/mta/studio-yourmt3 \
  --test-audio /path/to/authorized-musical-fixture.wav \
  --accept-apache-2-license
```

The recipe creates a separate CPU environment, downloads only pinned files, checks sizes/digests, converts the checkpoint to safetensors and runs actual inference before marking the runtime tested. ACE-Step/ROCm is unchanged. The original checkpoint download is 561,544,628 bytes; PyTorch and dependencies require additional storage. A clean Linux CPU installation was verified using a fully checked local source/weight cache and PyPI/PyTorch dependencies. The initial source download was refused by this environment network (403); the incomplete runtime was removed. Use `--source-cache /path/to/cache` with the full pinned source/checkpoint tree to avoid source-download fallback; all sizes/digests are still checked. Measured runtime size: 1,810,689,063 bytes. A real job was also submitted in the browser using the new runtime. Rocky/Windows/macOS remain untested.

Run the recipe as the MTA service/application account in a parent directory writable by that account. The private runtime belongs to that account; a root-owned mode-700 installation is not readable by a non-root service.

Apply the three variables printed after the test to the service/application and restart:

```text
MTA_STUDIO_TRANSCRIBER=yourmt3
MTA_STUDIO_YOURMT3_RUNTIME=/opt/mta/studio-yourmt3
MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON=/opt/mta/studio-yourmt3/bin/python
```

This selects the transcription backend for the instance. Audio-to-MIDI reuses the global queue, registered worker, CPU accounting, timeout/cancellation and atomic project import. Mono/stereo regions up to ten minutes are accepted. Actual notes are grouped by GM program with separate percussion; no filler parts are created. Manual program overrides and Basic Pitch thresholds do not apply.

To restore Basic Pitch, remove the transcriber and Python overrides while retaining its installed runtime. Stop active jobs before changing/removing runtimes. Graphical installation/uninstallation/default selection for YourMT3 remains open; existing Basic Pitch graphical administration is preserved.

### Verified result and limits

A locally synthesized, authorized four-second FluidSynth/FluidR3 GM piano fixture contained C4/E4/G4. All three pitches, onset/offset times and the piano program were recovered. The separate worker, MTA queue, approximately 17 CPU seconds, atomic import and saved-project reload were exercised. This is a technical workflow test, not a general music benchmark.

Velocity 96 is **generated**, not measured. No calibrated confidence, dynamics, CC, bend or articulation is fabricated. Players sharing a program are merged. ROCm/CUDA, real ten-instrument mixes, accurate/multimodel modes, reconciliation and alternative-review workflows remain unverified or unimplemented. Thirteen decoder channels do not guarantee thirteen correctly recognized instruments in a recording.

## Licenses and provenance

| Component | Source and conditions |
|---|---|
| Source and noPS checkpoint | Original-author Space, Apache-2.0 repository metadata, pinned revision above; source and weights from the same publication, not a mirror. |
| Original checkpoint | SHA-256 `ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25`; not redistributed in the ZIP. |
| Conversion | Mandatory original digest, `weights_only=True`, inert placeholders for training metadata, exactly 655 tensors / 47,081,642 elements. Inference never loads pickle. |
| T5 compatibility | Mathematical layers only, from Transformers v4.45.1, Apache-2.0; retained notice in `app/studio_assets/yourmt3_t5_compat.py`. Old download/deserialization code excluded; runtime Transformers 4.57.6. |
| Dependencies | PyTorch BSD-style; torchaudio BSD-2-Clause; NumPy BSD-3-Clause; Transformers/Lightning/W&B Apache-2.0; librosa ISC; einops MIT; safetensors Apache-2.0; mido/mir_eval/smart-open MIT; soundfile BSD-3-Clause with LGPL libsndfile. Recheck transitive/binary obligations for the distribution platform. |
| Datasets | No training datasets/audio redistributed. Model publication does not grant rights to arbitrary user inputs. |

Apache-2.0 text is retained in `app/studio_assets/Apache-2.0.txt`. MTA modifications are declared: tensor-only loader and compatible mathematical layer imports. Hugging Face/Transformers/W&B telemetry is disabled; offline inference never downloads additional models.

## Native audio devices

Settings → Audio devices / ASIO / routing selects PortAudio, host API, device, buffer and matrices. Output maps stereo master to up to 64 physical outputs; input maps up to 64 physical inputs to stereo recording. Independent per-track hardware buses remain open. Database preferences are local to the application; missing devices cause an error instead of silent replacement.

The hardware callback is compiled C++, without Python callbacks, allocation or locks. Playback and recording can share one duplex stream; overflow/disconnection fails explicitly. Compiled callbacks, matrices and a real PortAudio virtual ALSA stream were tested. Physical devices and Windows ASIO drivers are not certified.

ASIO SDK terms differ from VST3 MIT. The sounddevice wheel's ASIO DLL is excluded from automatic packaging until a verified corresponding-source/notice bundle is ready. Standard PortAudio remains included; operator-installed ASIO builds can be discovered by the sounddevice loader. Missing ASIO must not prevent application startup.

## Remote workflows

Native applications can route Audio-to-MIDI and MIDI harmonies to the configured server using the shared AI token. The server runs its selected model. A durable request journal recovers the same attested result after interruption, without a second execution/charge. Server usage is displayed locally without a duplicate local ledger. Harmony transport is bounded validated JSON, never local file paths.
