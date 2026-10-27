# Remote AI processing — server and client setup (r210)

## Current supported path: remote ACE-Step from an MTA server

MTA runs its existing authenticated `/api/projects/.../ai-arranger` and `/remix` endpoints on its local or remote web server. The ACE-Step worker can now connect to a **remote HTTPS** API with a trusted host and bearer token. The MTA app server renders selected WAV input, submits it to the server and validates downloaded output. The original tracks are preserved.

### ACE-Step GPU server

1. Install ACE-Step with `sudo ./install_ace_step.sh`; choose network binding only for a protected internal network.
2. Put ACE-Step behind an HTTPS reverse proxy with a trusted certificate, strong authentication and access restrictions (VPN/allowlisted clients). Never expose raw ACE-Step HTTP directly to the public Internet.
3. Ensure the ACE-Step API accepts `Authorization: Bearer ...`, or adapt the reverse proxy to enforce it. Generate/store the token securely; do not put tokens in MTA projects.
4. Forward the API endpoints `/health`, `/release_task`, `/query_result` and `/v1/audio` to the loopback ACE-Step service.
5. Restrict access using firewall or Proxmox policy, and confirm the worker's certificate trust chain.

### MTA Linux server

Install MTA using `sudo ./install_mta.sh --ace-url https://ace.internal.example:8443`; the wizard persists this URL and approved host. Put `MTA_ACE_STEP_TOKEN=<secret>` in `/etc/mta/mta.env` (`chmod 600`), and restart `mta-audio-editor.service`.

Or configure manually in the MTA process environment:

```ini
MTA_AI_WORKER_ENABLED=true
MTA_AI_WORKER_EXECUTABLE=/opt/mta/application/app/ace_step_http_worker.py
MTA_ACE_STEP_URL=https://ace.internal.example:8443
MTA_ACE_STEP_TRUSTED_HOST=ace.internal.example
MTA_ACE_STEP_TOKEN=REPLACE_WITH_API_KEY
```

The worker explicitly rejects remote HTTP, arbitrary/nonallowlisted hosts, redirects, invalid ports, embedded credentials and non-HTTPS network traffic. TLS certificates are verified by the Python HTTPS stack. If using a private CA, install the CA in the OS trust store or configure an approved CA bundle via standard Python SSL environment. **Do not disable TLS verification.**

A local SSH tunnel also works without HTTPS by pointing the worker to `http://127.0.0.1:8001` with a forwarded port.

### Native applications and API clients — current accounted transport

Connect the native installation through **Native AI processing → MTA server for all remote AI engines → Connect account**,using the MTA HTTPS origin (for example `https://mta.example.org`). Approve the instance with its original account. For Arranger/ACE select the MTA-account connection. Remote unavailability does not select local inference as fallback. Current model/regime rights remain enforced;commercial remote inference is still blocked without the required complete attestation.

External API clients use a personal bearer token with `POST /api/ai-jobs/execute-audio/ace-step` for WAV or `/api/ai-jobs/execute` for a self-contained JSON plan. Persist an original `X-MTA-AI-Idempotency-Key` before submission. Recover lost responses through original-owner request status/result/history;do not submit another inference. Never send host file paths or executable commands.

### Legacy gateway migration

`/api/ai-gateway` now permits only authenticated GET health/model metadata. Raw generation/init and unbound upstream task polling/audio retrieval are refused before upstream transport. HTTP wall time/traffic are not resource measurements. Existing accounted requests/results remain accessible under `/api/ai-jobs`;a historical raw task without account/ledger proof cannot be automatically adopted or rebilled. Preserve its files/journals for isolated operator reconciliation.

Forward `/api/ai-jobs/*` unchanged through HTTPS to **MTA**,preserving Authorization and request headers. Keep raw ACE-Step private. The old `/api/ai-gateway` URL is not an inference/download endpoint for native clients. See `LEGACY_EXECUTION_BOUNDARIES_R210.md` for IT/EN migration,exact regression evidence and acceptance limits,and `REMOTE_AI_REVERSE_PROXY.md` for proxy examples. This documentation is not confirmation of a deployment or certification of every optional runtime.
