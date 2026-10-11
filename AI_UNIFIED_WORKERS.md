# Central AI worker adapters (r207)

The authenticated execution endpoint now supports a **strictly server-configured registry** of model families: `ace-step`, `arranger`, `remix`, `whisper`, `demucs`, `singer-separation`, `backing-vocals`, `drumsep`, `sam-audio`, and `chords-ml`.

This is a unified execution **contract**, not a claim that the individual inference engines have been migrated. To activate a family, an administrator must install an adapter executable that supports the existing JSON request and WAV result protocol. Most models (for example Whisper transcription and chord detection) naturally return JSON or text and will need dedicated output adapters before their native features can use this endpoint. Existing local UI/API routes do **not** automatically move to the unified registry.

Set `MTA_AI_WORKER_ENABLED=true` and, for each family, `MTA_AI_WORKER_<KIND>_EXECUTABLE=/absolute/path/to/adapter.py`, with hyphens replaced by underscores. Examples:

```
MTA_AI_WORKER_WHISPER_EXECUTABLE=/opt/mta/workers/whisper_adapter.py
MTA_AI_WORKER_DEMUCS_EXECUTABLE=/opt/mta/workers/demucs_adapter.py
MTA_AI_WORKER_SAM_AUDIO_EXECUTABLE=/opt/mta/workers/sam_adapter.py
```

ACE-Step retains backward compatibility with `MTA_AI_WORKER_EXECUTABLE`. All configured paths must be absolute, regular, executable and not symlinks. The HTTP client cannot specify an executable, command line, output path or host file path.

Authenticated endpoints (bearer token issued by the MTA server):

- `GET /api/ai-jobs/worker-capabilities`: check configured adapters.
- `POST /api/ai-jobs/execute`: self-contained JSON with `kind` and `plan`; returns WAV and `X-MTA-AI-Job-ID`.
- `POST /api/ai-jobs/execute-audio/{kind}`: raw WAV body (`audio/wav`) up to 32 MiB, returns WAV and `X-MTA-AI-Job-ID`. MTA validates the uploaded WAV and creates its own private per-job input path; the worker receives that input as `source_audio` in the JSON request.

Each execution creates an accounting job owned by the authenticated token's user, invokes the administrator-controlled worker in an isolated temporary directory, and finalizes usage through existing CPU/cgroup billing safeguards. GPU-seconds billing remains disabled without trusted job-complete GPU telemetry. Temporary input and output files do not count as persistent storage usage.

## Known limitations

- The generic response is WAV only. Lyrics/chord timestamps, multiple Demucs stems, and other structured/multi-file results are **not yet transported** by this route.
- The preexisting Whisper, Demucs, SAM, singer, lyrics and chords UI routes are **not yet migrated** onto it. Those requests can still run locally and are not covered by central-job accounting.
- A model adapter is required for each family; a registry entry alone does not install its ML dependencies or enable it.
- Real GPU process telemetry and end-to-end multiuser benchmark validation remain required for consumption-grade billing.

Do not enable the central service directly on the public Internet: deploy behind TLS reverse proxy, configure authentication, and keep the ACE-Step worker on a trusted private network.

## Multi-artifact worker result (incremental r207 update)

A server-configured worker may now write `output.manifest.json` alongside its
artifacts in the private job directory instead of a single `preview.wav`.
The manifest format is `{"version":1,"files":[{"name":"vocals.wav","type":"audio/wav"},{"name":"lyrics.json","type":"application/json"}]}`.
Permitted MIME types are `audio/wav`, `application/json`, `text/plain`.
The server checks basename-only filenames, rejects symlinks/duplicates,
validates JSON and WAV, and caps the bundle at 64 MiB and 16 files.
The result is `application/zip` with `manifest.json`, while a legacy single-WAV
adapter continues returning `audio/wav`. The `worker-capabilities` endpoint
advertises both formats. All generated files are temporary.

**Still incomplete:** The stock Whisper, Demucs, SAM, DrumSep and chord-processing
implementations do not automatically emit this manifest. Model-specific
adapters, native client routing and comprehensive end-to-end regression tests
are still required before universal remote execution can be claimed.

## Per-model parameters accompanying WAV uploads (r207)

`POST /api/ai-jobs/execute-audio/{kind}` accepts an optional
`X-MTA-AI-Options` header containing base64url-encoded UTF-8 JSON object
(maximum 8192 decoded bytes). For example `{"language":"it","model":"medium"}`
for transcription, or `{"stems":4}` for a separator. The server validates the
header and adds these settings to the worker's JSON plan. Clients cannot
specify `source_audio`, filesystem paths, executables, command or shell.
The source WAV is staged by MTA in a private temporary directory and its
server-side path always overrides client-supplied data.

This does **not** mean model-specific adapters or the existing native UI
functions have been migrated. The administrator must provide audited adapters
and native call sites must explicitly use the authenticated remote endpoint;
otherwise those legacy functions still execute locally. No full end-to-end
GPU or native-client execution validation has been performed in this package.

## r207: built-in opt-in inference adapters

On the **server** set `MTA_AI_WORKER_ENABLED=true` and
`MTA_AI_UNIFIED_WORKERS_ENABLED=true` to use `app/ai_unified_adapter.py` as the
operator-approved adapter for `whisper`, `demucs`, `drumsep`, `sam-audio`,
`chords-ml`, `singer-separation` and `backing-vocals`. Each backend requires its
own optional model/dependencies on the **server**; unavailable dependencies fail
explicitly. ACE-Step/Arranger/Remix continue to use their separate existing
configured adapters. Users may not supply arbitrary commands or server paths.

Models that need configuration:
- DrumSep: `MTA_AI_DRUMSEP_MODEL=/absolute/path/model.onnx`
- SAM Audio: `MTA_AI_SAM_MODEL=<trusted installed model identifier>`
- Vocal separator: `MTA_AI_VOCAL_MODEL=<installed filename>` and optionally
  `MTA_AI_VOCAL_MODELS_DIR=/absolute/path/to/models`
- Whisper and Demucs rely on installed optional Python dependencies.

The remote audio endpoint `/api/ai-jobs/execute-audio/{kind}` accepts WAV and
responds with a validated archive containing output WAV files, JSON transcripts
or chords. These backends run in the central metered subprocess executor.

**Important scope:** the legacy MTA project-facing endpoints for lyrics/stems
continue to use their original local worker code, and native clients do not yet
universally select the central endpoint for every AI feature. Installing the
adapters does not by itself reroute these pre-existing UI actions. Verify each
feature in both local and remote mode before deploying client devices without
local AI runtimes.

## Authenticated multiuser concurrency smoke test

On a client or on the server, create a private JSON file (mode 0600) with tokens
for at least two **test** users:

```json
{"users":[{"label":"test-a","token":"REPLACE_A"},{"label":"test-b","token":"REPLACE_B"}]}
```

```sh
chmod 600 /secure/path/test-ai-tokens.json
bash scripts/install_ace_step.sh --benchmark-concurrent \
  --benchmark-remote-url https://mta.example.org \
  --benchmark-tokens-file /secure/path/test-ai-tokens.json \
  --benchmark-jobs-per-user 2 \
  --benchmark-output ./ai-concurrency-report.json
```

This runs simultaneous short WAV requests against the remote Whisper adapter.
The JSON report contains job IDs, response status, duration, and user **labels**,
never token values. The test confirms unique job IDs and successful transport;
**it does not certify** CPU/GPU measurements or ownership from the client.
Afterwards, the administrator must compare each returned job ID against its
user in `/admin/ai-billing`, check cgroup CPU measurements and GPU diagnostic
quality, and verify that persistent storage accounting excludes temporary
inputs and outputs. Avoid concurrent production jobs during a controlled GPU
baseline test. The report contains no WAV inputs or transcripts.

## Native remote-mode acceptance checks

On Windows, macOS, and Linux separately: select remote mode and a remote server;
restart the application; verify persisted mode; perform ACE-Step generation,
Whisper lyrics, Demucs stems and all other enabled features. Confirm remote job
IDs in the server ledger and **no local model processes, downloads, or GPU memory
allocation**. Repeat in local mode and check local execution. At present only
the ACE-Step-specific native connection is integrated; other native features
must not be advertised as universally remote until their existing project/API
routes and client UX are migrated and tested end-to-end.

### Native HTTPS transport (r207 cumulative)

`app/ai_remote_client.py` provides `infer_audio(base_url, token, kind, wav,
options)` for native/Desktop integrations. It accepts an MTA HTTPS base URL
or `/api/ai-gateway` and targets `/api/ai-jobs/execute-audio/{kind}`.
Returns bytes, the response media type (WAV or ZIP), and the registered job ID.
The server token is never appended to a URL. Input/output are both capped at
32 MiB. Invalid/missing job IDs and network failures raise `RemoteAIError`;
no local model or worker is started as fallback.

**Integration gap:** historical desktop browser views and their specialized
API routes have not yet been switched over to this shared transport. The
actual remote/local selection and mapping of Whisper lyrics JSON, separated
stems ZIP and chord timestamps into the project remain necessary. Native
end-to-end tests require Windows, macOS and Linux builds.

## r207 native opt-in per model (Windows/macOS/Linux)

From native **Settings → AI local / remote workers**, choose Local or Remote
independently for Whisper/lyrics, chord analysis, Demucs, DrumSep, SAM Audio,
singer separation, and backing vocals. In Remote mode, set the MTA HTTPS
server URL and a personal AI token. A saved token is never returned by the
settings API. The native runtime persists the settings in a private JSON file
(mode 0600) and the backend reads them before each job.

Legacy project routes for lyrics/chords, stem separation, and optional
post-stem lyrics/chords now invoke the remote transport when that model's
remote mode is enabled. JSON results are validated into LyricLine/Chord
objects, and WAV stems are staged into private temporary job folders. The
SAM Audio, DrumSep and lead/backing helpers also inspect per-model mode.
Remote failure does **not** trigger a local model fallback. All these
routes still require runtime evaluation with real inference dependencies and
native build artifacts.

The remote server must have `MTA_AI_WORKER_ENABLED=true` and
`MTA_AI_UNIFIED_WORKERS_ENABLED=true` (and the appropriate model/runtime
installed); it authenticates the personal token and registers each remote
job for accounting. Composite pipelines can create multiple remote jobs;
therefore the accounting report must reconcile their remote job IDs.

Current limits: direct/legacy AI routes not covered by these project workflows
may still require model-specific verification. Files larger than the remote
upload/response transport limits require a future streamed upload protocol.
AMD/NVIDIA GPU accounting is not yet certified without the hardware benchmark.

## Native opt-in routing audit (r207 cumulative, October 2026)

Native single-user mode provides **independent** local/remote settings for `whisper`, `chords-ml`, `demucs`, `drumsep`, `sam-audio`, `singer-separation` and `backing-vocals` through the application Settings panel (Native AI processing) and `/api/native/ai-workers/settings`. The secret bearer token is saved locally with restricted permissions and is never included in `GET` responses. A remote setting is used **only when the corresponding inference operation is requested**; it does not cause eager model startup or downloads.

Remote lyrics and chords decode `transcript.json` and `chords.json`; Demucs imports returned WAV stems into the project; DrumSep selects the requested instruments; SAM Audio imports a WAV; backing-vocal separation consumes two vocal stems; singer separation requests the selected singers together and matches the `singer_N.wav` outputs, rejecting missing singers. Each operation fails explicitly if remote inference fails and **does not fall back to local inference**. Compound workflows retain separate local/remote decisions for their constituent workers (e.g., Demucs followed by DrumSep).

This audit is based on source-level routes and mocked transport tests, not on an end-to-end Windows/macOS/Linux package or model-loaded GPU system. Confirm installed models/worker options and the remote accounting job IDs in an environment with MTA Server. Limits: 32 MiB audio request and result payload per operation; large recordings need a streamed upload API in a follow-up revision.
