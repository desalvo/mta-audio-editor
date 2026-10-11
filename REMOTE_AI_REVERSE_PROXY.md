# MTA + ACE-Step remote AI access through one HTTPS reverse proxy (r207)

## Architecture and client endpoint

```text
Native MTA client or browser
   HTTPS 443 + per-user AI bearer token (native AI requests)
              |
      Kubernetes Ingress NGINX / HAProxy, or Docker HAProxy
              | all paths incl. /api/ai-gateway/*
              v
       MTA app web server (VM/LXC private-IP:8080)
        | authenticates token; records per-user usage
        v
       ACE-Step (127.0.0.1:8001, private ONLY)
```

**Browser:** `https://mta.example.org/` and normal MTA user login. **Native ACE-Step remote configuration:** base URL `https://mta.example.org:443/api/ai-gateway` and individual bearer token (`mta_ai_...`) issued by the MTA admin in **`https://mta.example.org/admin/ai-tokens`**. The native app keeps its own MTA backend locally; only ACE-Step processing is sent over HTTPS. The worker automatically calls `${BASE}/release_task`, `${BASE}/query_result` and `${BASE}/v1/audio`. The proxy must preserve those paths, headers, request bodies and HTTP methods, with **no rewrite**. The gateway authenticates the bearer token on every request and does **not** pass it through to raw ACE-Step.

## Configure VM/LXC

Install ACE-Step using `sudo ./install_ace_step.sh --bind local --port 8001` and MTA using `sudo ./install_mta.sh --bind network --port 8080` (check supported flags with `--help`). Configure MTA's root-only `/etc/mta/mta.env` with `MTA_ACE_STEP_URL=http://127.0.0.1:8001`, `MTA_AI_WORKER_ENABLED=true` and a valid `MTA_AI_WORKER_EXECUTABLE`. Restart the MTA service. In Docker/Kubernetes proxy scenarios, open TCP 8080 **only between proxy/Ingress nodes and the VM/LXC**, not from the internet. Ensure ACE-Step's TCP 8001 is NOT reachable from external clients. Public DNS resolves `mta.example.org` to the proxy, not to the VM. Use HTTPS with a trusted certificate; put no shared key in ingress annotations.

## Kubernetes (proxy only, backend VM/LXC)

The YAML files in `deploy/remote-ai/kubernetes/` create a selectorless Service and manual EndpointSlice pointing to the VM/LXC, plus alternative Ingress definitions:

1. Replace `192.0.2.50` in `backend.yaml` with the routable private IP and confirm CNI/ingress pods can connect to it on port 8080. The IP must not be `127.0.0.1` or a Kubernetes Pod address.
2. Create `mta-tls` TLS Secret in namespace `mta-external` using your normal certificate manager or a trusted issuer. Point `mta.example.org` DNS to the Ingress controller's public address.
3. `kubectl apply -f deploy/remote-ai/kubernetes/backend.yaml`
4. Choose exactly ONE ingress: `kubectl apply -f deploy/remote-ai/kubernetes/ingress-nginx.yaml` for community ingress-nginx class `nginx`, OR `kubectl apply -f deploy/remote-ai/kubernetes/ingress-haproxy.yaml` for class `haproxy`. The IngressClass must match the controller installed in your cluster.
5. Restrict traffic to the backend VM with firewall/security groups. Ingress exposes only MTA; it NEVER proxies raw ACE-Step directly.

The NGINX example includes body size and long timeouts. The HAProxy Ingress controller example uses standard Kubernetes Ingress objects; ensure the installed controller has suitable upload limits and read/write timeouts for large audio files, configured via that controller's documented ConfigMap/annotations. Both proxies route all paths unchanged. The application gateway currently limits each AI request body to **32 MiB**; audio larger than this will be rejected with HTTP 413 even if the Ingress allows a larger size.

## Docker HAProxy without Kubernetes

1. Edit `deploy/remote-ai/docker-haproxy/haproxy.cfg`: replace `mta.example.org` and `192.0.2.50:8080` with the hostname and private MTA target.
2. Install a trusted PEM containing certificate and private key at `deploy/remote-ai/docker-haproxy/certs/mta.pem` (protect private key; do not commit it). Configure DNS and allow ingress TCP 443 to the proxy.
3. `cd deploy/remote-ai/docker-haproxy && docker compose up -d`.
4. Confirm `https://mta.example.org/api/health` returns a successful result, then from a native client test the AI gateway. No public 8001 port is necessary.

## Token lifecycle, resource accounting and billing readiness

MTA admin issues multiple independent tokens for active MTA users in `/admin/ai-tokens`, each with a label identifying client/device. Tokens are shown only on issuance and are stored hashed; the administrator can rotate or revoke individual tokens. `GET /api/admin/ai-usage` returns per-user counts, elapsed HTTP wall time and byte totals; `GET /api/account/ai-usage` shows a user's own totals. **CPU seconds, GPU seconds and energy are NOT yet measured or attributed**: parallel workloads and queue time would make HTTP wall time materially different from billable utilization. Do not use wall time for billing. A job-aware scheduler/worker with CPU and GPU process counters, shared-GPU attribution, durable job IDs, quotas and audited rates is needed before billing.

## Security checklist and diagnostics

- HTTPS termination must preserve `Authorization: Bearer <user token>` through to **MTA**. Never route `/api/ai-gateway/` directly to ACE-Step.
- Restrict MTA backend port 8080 to proxy networks. Never expose ACE-Step port 8001. Separate internal ACE-Step authorization can be configured independently.
- Do not enable `MTA_ALLOW_INSECURE_NO_AUTH` for network-facing MTA; keep standard MTA login enabled.
- Client token errors: 401 unauthorized/revoked; 404 path not allowed; 413 body too large; 502 ACE-Step connection failure. A browser login session alone does not authorize the gateway API; a dedicated AI token is required.
- `curl --fail-with-body https://mta.example.org/api/health` tests the MTA site; `curl -i -H 'Authorization: Bearer YOUR_USER_TOKEN' https://mta.example.org/api/ai-gateway/health` tests token authentication and routing. Do not print actual tokens in build logs.
