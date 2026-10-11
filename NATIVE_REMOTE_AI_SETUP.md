# ACE-Step: local or remote in native MTA

In the AI Arranger/Remix panel, first use asks for **Local** or **Remote** ACE-Step. The choice remains editable in the same native-only settings panel. Native MTA always launches its local web UI server; only AI computation is delegated.

## Remote backend

1. Deploy ACE-Step to a dedicated GPU host using `scripts/install_ace_step.sh`; prefer loopback behind a reverse proxy.
2. Publish a validated TLS HTTPS endpoint with an API bearer token, e.g. `https://ace.example.org:8001`. Use an access-controlled network. Direct publicly accessible inference is not recommended.
3. In native MTA, open AI Arranger/Remix and choose **Remote**. Enter the exact HTTPS URL and bearer token, then save. New requests are submitted via the installed MTA worker and WAV source audio is transmitted to the remote endpoint. Audio results return to MTA as non-destructive new tracks.
4. Check remote firewall, TLS certificate trust and API server authorization. The chosen address must not redirect.

No ROCm or model download is needed on the client for ACE-Step. A saved remote token is stored under the current user's MTA data directory in `connection.json` with restrictive file permissions where supported. It is not returned by status APIs. Protect the user profile and avoid sharing backups of this file. Switching to local stops only an MTA-managed process.

**Security:** The remote endpoint must implement compatible bearer authorization; ACE-Step proxy/installation should be tested on the actual distribution. HTTPS alone does not provide authorization. Native desktop settings are single-user only.

## Locale / Local

Select **Local**, then use Install/Start from the same panel. Permission for model downloads is explicitly requested; MTA does not automatically install the models on first launch. You can change modes later.

This feature delegates ACE-Step processing. Other MTA AI providers, and use of an entirely remote MTA web server instead of the native embedded MTA server, are not automatically configured by this choice.

## Recommended unified public endpoint (MTA AI gateway)

For per-user authorization and accounting, **do not expose ACE-Step's raw API**.
Use `https://mta.example.org:443` for the MTA UI, and **`https://mta.example.org:443/api/ai-gateway`** as the **ACE-Step endpoint** in native clients. Copy an individual `mta_ai_...` bearer token issued from MTA administration; never use the private ACE-Step service key on a client. The application forwards `POST /release_task` to `POST /api/ai-gateway/release_task`, and so on. The HTTPS proxy forwards ALL `/api/ai-gateway/*` requests to **MTA**, not directly to ACE-Step.

On the backend, `MTA_ACE_STEP_URL=http://127.0.0.1:8001` (same VM/LXC) and `MTA_AI_WORKER_ENABLED=true`. Bind ACE-Step to loopback; the MTA web server may bind to the VM/LXC's private IP for reverse proxy access. External clients only access MTA's HTTPS origin.

Usage currently records authenticated request count, wall duration and bytes per user. `cpu_seconds`, `gpu_seconds` and `gpu_energy_joules` are nullable, **not measured yet**, therefore not suitable for billing. A task-aware GPU/CPU measurement collector will be required for chargeable usage.

See `REMOTE_AI_REVERSE_PROXY.md` for complete Kubernetes and Docker examples.
