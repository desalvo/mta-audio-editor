# Remote AI processing — server and client setup (r207)

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

### Client devices and native applications — current limitation

Browser clients can access a remote authenticated **MTA web server**, so the server performs ACE-Step inference without installing models on the browsing device. Existing native Windows/macOS/Linux packages, however, start a **local** MTA service and are **not yet wired** to switch all AI tasks to a remote MTA server through an in-app setting. This release does not implement a general-purpose remote inference mode for Demucs, Whisper, chord analysis or every other AI feature. Such a mode requires authenticated project/audio transfer and asynchronous job/result handling in the native client; a server URL alone does not make those operations remote.

Do not expose API access tokens to browser JavaScript or ship shared credentials with native binaries. Use user/session authentication to the MTA server and ensure access control on each project and job.

## Recommended unified public endpoint (MTA AI gateway)

For per-user authorization and accounting, **do not expose ACE-Step's raw API**.
Use `https://mta.example.org:443` for the MTA UI, and **`https://mta.example.org:443/api/ai-gateway`** as the **ACE-Step endpoint** in native clients. Copy an individual `mta_ai_...` bearer token issued from MTA administration; never use the private ACE-Step service key on a client. The application forwards `POST /release_task` to `POST /api/ai-gateway/release_task`, and so on. The HTTPS proxy forwards ALL `/api/ai-gateway/*` requests to **MTA**, not directly to ACE-Step.

On the backend, `MTA_ACE_STEP_URL=http://127.0.0.1:8001` (same VM/LXC) and `MTA_AI_WORKER_ENABLED=true`. Bind ACE-Step to loopback; the MTA web server may bind to the VM/LXC's private IP for reverse proxy access. External clients only access MTA's HTTPS origin.

Usage currently records authenticated request count, wall duration and bytes per user. `cpu_seconds`, `gpu_seconds` and `gpu_energy_joules` are nullable, **not measured yet**, therefore not suitable for billing. A task-aware GPU/CPU measurement collector will be required for chargeable usage.

See `REMOTE_AI_REVERSE_PROXY.md` for complete Kubernetes and Docker examples.
