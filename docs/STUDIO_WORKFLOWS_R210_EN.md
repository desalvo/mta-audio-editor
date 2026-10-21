# Studio workflows and MIDI controllers — 0.3.0-r210

The new workflows run real workers on the existing global queue and save results in real MTA projects. **The complete AI Vocal Studio and Multi-Track Audio-to-MIDI specifications are not finished.** MIDI harmony is not synthetic singing, and Basic Pitch is not a full-mix instrument classifier.

| Feature | Actual status |
|---|---|
| Independent audio sources → MIDI | Implemented; real ONNX CPU tests. Up to 32 selected sources, maximum ten-minute region per job. No drums or automatic instrument identification. |
| MIDI melody → harmonized MIDI | Implemented; real worker tests. 2–8 parts, SATB-style voice leading, configurable ranges through API, confirmed chords take precedence. No rendered singers. |
| Audio → MIDI → harmony → project reopen | Locally verified with two synthetic audio sources and real ONNX inference; four harmony parts and CPU ledger consistency. Not a real-song accuracy benchmark. |
| Graphical controller lanes | Chromium verified: CC, 14-bit bend, channel/polyphonic pressure and programs; multiple selection, keyboard/drag, snap, undo/redo and persistence. |
| Singing/conversion, lyrics/phonemes | Not implemented; no verified authorized IT/EN/FR voicebank integrated. Singers/Expression tabs explicitly explain this limitation. |
| Full-mix multitrack classification/reconciliation | Not implemented. Import/editor capacity for at least 16 independent parts does not imply model recognition capacity. |
| Dedicated ASIO and complete physical I/O matrix | In development, incomplete; no hardware certification. |

## Install and administer

Open a project, **MIDI → AI Multi-Track Audio-to-MIDI → Execution → Studio models and settings** as administrator. Review the linked licenses, accept explicitly and choose **Install and test**. Merely opening the dialog performs no implicit model download.

The fixed recipe installs a separate Python 3.11/3.12 CPU environment below the application's data directory, `.studio-models/basic-pitch-0.4.0-onnx-v1`. It does not replace the existing server/ROCm environment. Package-index access, storage and a compatible Python are required. Native builds with newer Python need an accessible Python 3.11/3.12; automatic installation of that interpreter remains open.

Activation follows model checksum verification and a real reference-tone inference. Installation reports phases and terminal state, without invented pip/inference percentages. Administrators can run a fresh inference test, enable/disable or uninstall. Active/queued Studio work prevents removal; a runtime lock also protects remote worker inference. The test verifies reference-tone detection, not general musical accuracy or ROCm/CUDA compatibility.

ONNX is forced to CPU, with bounded thread counts. `ORT_DISABLE_TELEMETRY=1` is set before import/initialization; the runtime telemetry-disabling API is also called. The source ZIP contains no model weights or installed Python environments.

## Run, close, cancel and import

1. Choose source tracks and a region in milliseconds. Audio preparation respects non-destructive clips, source/timeline offsets, delay and gain. It does not apply track inserts or pitch/time-stretch mix processing. Imported MIDI retains the region offset.
2. Set transcription thresholds or harmony voice count/key. Instrument programs are editable afterward; the model does not invent classifications.
3. Start through the global queue. Server authentication, project permissions, quota/credit admission and accounting remain active. Exhausted credits reject work before launching the worker and direct the user to their profile or administrator.
4. Closing the dialog leaves the job running; use All jobs to inspect/cancel it. Cancellation stops workers. Once atomic publication starts, cancellation is explicitly refused until publication completes.
5. Automatic import saves tracks before terminal success if the project remains unchanged. A changed project retains the result for explicit review and import against the current revision. Replaying the same publication cannot duplicate tracks.
6. Download the shared musical JSON or authorized diagnostics ZIP containing job state, counters and publication receipt. Source audio and credentials are not included. Detailed server worker stderr remains in the existing server diagnostic journal.

Retry reuses completed source checkpoints only for the same user/project, identical request and source revision. It reruns unfinished phases; it does not resume internal neural-network state. Modified projects require fresh computation. Results/cache expire after seven days by default (configurable 1–365), with cleanup at startup and hourly for terminal jobs or expired orphan directories. Saved project media remains intact. Full account-data deletion also removes Studio caches. Last-job preferences are separate per project and operation and use lazy DB persistence.

Job timeout defaults to 3,600 seconds (configurable 60–14,400). CPU usage from authenticated workers is reflected in queue/ledger; missing GPU measurements are not manufactured. Native single-user execution creates no server bill. Token clients can use the existing remote worker endpoint; complete new local-project Studio workflows routed to a remote server remain open.

## Controller lanes

Open **Controller lanes** in the MIDI editor. Choose event type/channel and CC or note number. Double-click or numeric fields add points. Shift-click selects multiple points; drag or arrow keys move the group. Alt bypasses snap, Delete removes, Ctrl/Cmd-Z undoes. Pitch bend raw values span 0–16383, centered on 8192; the graph shows signed bend. Curves show actual stepwise MIDI values, without hidden interpolation. The lane shares piano-roll zoom and horizontal scroll. Edits affect the same events used by the event list, saving and SMF export.

## API and isolation

- `GET /api/ai/studio/capabilities` reports actual installed capabilities and unavailable candidates.
- `POST /api/projects/{pid}/ai-studio/jobs` accepts operation, track_ids, region, settings, auto_import and optional retry_of. Callers cannot select executables or file paths.
- Project job endpoints: `GET .../jobs/{job_id}`, `POST .../cancel`, `GET .../result`, `POST .../import`, `GET .../diagnostics.zip`.
- Admin endpoints under `/api/admin/ai/studio`: models, policy, Basic Pitch install/test, enable/disable and uninstall.

Structured scores use a validated private file up to 8 MiB, separate from the small worker request. Musical JSON is limited to 16 MiB and the shared event/24-hour budgets. Workers reuse existing artifact and metering checks.

## License and model review

Primary sources checked 20 October 2026; code, weights, voicebanks, data and dependencies require separate review. Worker isolation does not itself resolve copyleft or voicebank rights.

| Candidate | Decision/evidence |
|---|---|
| Basic Pitch | Upstream code and included ONNX model Apache-2.0. Model SHA-256 `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`. Recheck transitive binary/dependency obligations before distribution. |
| YourMT3 | Original repository GPL-3.0. External checkpoint rights and reproducible dependency integration unresolved here; not enabled. |
| MT3-Infer | MIT wrapper, but upstream explicitly describes vendored MT3-PyTorch code as license-frozen without a declared license. Not installed. |
| OpenVPI vocoders | Some pretrained releases explicitly CC BY-NC-SA-4.0; not activated for a billed service. Vocoder and singer rights are separate. |
| Other singing/transcription candidates | Not enabled without fixed versions, authorized weights/voicebanks, a reviewed recipe and real inference/hardware validation. |

Sources: https://github.com/spotify/basic-pitch/blob/main/LICENSE ; https://github.com/mimbres/YourMT3 ; https://github.com/openmirlab/mt3-infer ; https://github.com/openvpi/vocoders/releases ; https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md .

Remaining: authorized singing/conversion and phoneme/lyrics integration; multimodel transcription, reconciliation and alternative review; real comparable musical datasets; cross-platform optional GM installer; dedicated ASIO and physical routing; full native-platform and production ROCm acceptance. Local CPU/browser tests do not certify the installed production server.
