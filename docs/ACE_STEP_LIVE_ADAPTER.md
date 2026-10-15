# ACE-Step 1.5 live adapter (r187)

Experimental adapter `app/ace_step_http_worker.py` uses the upstream ACE-Step 1.5 asynchronous HTTP API: multipart POST `/release_task` with staged WAV as `src_audio`, POST `/query_result`, and GET `/v1/audio`. It uses `task_type=cover` for an audio-conditioned version. **This is NOT a certified instrument-swap model and does NOT guarantee preservation of melody, vocal or chords.** No model dependencies or weights are bundled.

1. Install and run the official ACE-Step 1.5 server locally, separately, following upstream instructions: https://github.com/ace-step/ACE-Step-1.5 . Configure it to accept requests on `127.0.0.1:8001` (or tunnel a remote instance to loopback). Check license of installed dependencies/weights.
2. Create a trusted executable launcher outside any user-writable project, e.g. `/usr/local/bin/mta-ace-step-worker` with `#!/bin/sh` and `exec /path/to/python /path/to/MTA/app/ace_step_http_worker.py "$@"` and make it executable. The server application must be restarted after configuration changes.
3. Configure the MTA server environment: `MTA_AI_WORKER_ENABLED=true`, `MTA_AI_WORKER_EXECUTABLE=/usr/local/bin/mta-ace-step-worker`, `MTA_ACE_STEP_URL=http://127.0.0.1:8001`, optional `MTA_ACE_STEP_TOKEN` and `MTA_ACE_STEP_POLL_SECONDS`.
4. Select a **single track** or **Master Out**, choose ACE-Step, click Generate + Add track. The output WAV will be validated by MTA and added non-destructively if the upstream API returns a supported WAV.

The adapter cannot accept multi-source manifests, non-WAV input, or promise stem separation. Master Out is a single rendered WAV honoring track/master signal routing and effects. Instrument swap instructions are only text constraints; dedicated source separation and validation are needed before claiming selective replacement. The adapter is **not production certified**: verify device drivers, RAM/VRAM, ACE-Step installation, preservation quality and complete end-to-end inference on the target machine.

## Interpreting the controls

`strength=0` means adhere closely to the source; `strength=100` means transform more freely. It maps inversely to ACE-Step `audio_cover_strength` (1.0 down to 0.0). The output is a regenerated **single audio track** rather than individually editable generated stems. The API cannot guarantee preservation of chords, vocal identity or structure. No production certification is implied by protocol tests.

The MTA native engine remains experimental: `native_host_ready=false`. r187 also adds a bounded finite PCM block guard as a native DSP utility, **not** a replacement for full real-time VST3 host validation.

### r188 server check
Run `python -m app.ace_step_http_worker --check-server` on the MTA host after setting `MTA_ACE_STEP_URL`. This checks API reachability only, **not** successful inference. Use a real audio end-to-end test to certify operation.

**Executable setup:** configure `MTA_AI_WORKER_ENABLED=true` and `MTA_AI_WORKER_EXECUTABLE` to the absolute path of `app/ace_step_http_worker.py` (mark executable and ensure Python dependencies are available). Set `MTA_ACE_STEP_URL` to a loopback-hosted ACE-Step endpoint. An executable handshake or HTTP health check does not certify actual audio inference. Never expose an unauthenticated model server on a public interface.
