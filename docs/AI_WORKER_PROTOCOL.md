r181: With MTA_AI_WORKER_ENABLED=true and an absolute MTA_AI_WORKER_EXECUTABLE, authenticated POST /api/projects/{pid}/ai-arranger/generate and /remix/generate invoke worker --request/--output and return verified WAV. This does NOT automatically supply project audio to the model: worker adapter must resolve authorized project content. Job progress, cancellation of running generation, and production-grade isolation remain future work.

# External AI worker protocol / Protocollo worker AI

An administrator must explicitly set `MTA_AI_WORKER_ENABLED=true` and `MTA_AI_WORKER_EXECUTABLE=/absolute/path/to/trusted-executable`. This is a **low-level adapter**, not a deployed ACE-Step/DiffRhythm model. The configured executable receives `--request /path/request.json --output /path/preview.wav`. The request contains an AI plan; the output must be valid uncompressed PCM WAV (mono/stereo, 44.1/48/96 kHz, 16/24/32-bit, up to 30 minutes). Its result is validated before publication. Execution occurs outside the realtime audio callback.

**Security:** never accept executable paths from API users; install trusted adapters only. Production use additionally needs source-audio staging, job persistence, authorization for previews, cancellation during inference, resource quotas and an end-to-end model integration. In r180 the API generation endpoints intentionally remain unavailable (503); this protocol is testable independently.

**Italiano:** l'adattatore è attivato solo dall'amministratore; non fornisce da solo generazione ACE-Step. La generazione in UI continua a non essere disponibile. Occorrono integrazione con i file audio di input, persistenza dei job, gestione delle risorse e anteprima autenticata.

## r183 capability handshake
An administrator-configured worker may optionally respond to `--capabilities` with a JSON object like `{"protocol":"mta.ai.worker.v1","models":["ace-step-1.5"],"supports_audio_input":true}`. This checks only the protocol, never inference success. Failures are reported as `probe_ok=false`.

## r186 bounds
The source-audio manifest remains server-owned. Inputs longer than 30 minutes and preview output exceeding four times source duration (minimum allowance 15 seconds) are rejected. The configured model must still perform a real end-to-end inference acceptance test.
