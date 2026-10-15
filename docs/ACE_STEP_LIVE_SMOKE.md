# ACE-Step live smoke test (r192)

This opt-in check **actually requests a generated audio file**, unlike the health and capability probes. It requires a running, installed ACE-Step 1.5 server with loaded checkpoints. No model weights are bundled with MTA.

Configure the trusted executable and local server, then run:

```bash
export MTA_AI_WORKER_ENABLED=true
export MTA_AI_WORKER_EXECUTABLE=/absolute/path/to/ace_step_http_worker_executable
export MTA_ACE_STEP_URL=http://127.0.0.1:8001
python -m app.ace_step_live_smoke --seconds 5 --timeout 1200
```

The executable must be the installed, runnable MTA ACE-Step HTTP worker adapter (with proper Python import paths), not the upstream ACE-Step server executable. The worker supports `--smoke-input <file> --output <file>`; the test creates a synthetic sine-wave WAV in private storage. The result is a JSON document; `verified=true` indicates that the adapter returned a decodable WAV. It **does not** validate musical fidelity, preservation of chords or instrument replacement. Failure is indicated by nonzero exit status and a reason.

Use a private GPU-capable machine and make sure the ACE-Step sidecar or local server is accessible. The smoke test performs real inference and can consume substantial time and compute resources.
