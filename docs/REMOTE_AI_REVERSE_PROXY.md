# MTA + ACE-Step remote AI access through one HTTPS reverse proxy (r207)

## Architecture and client endpoint

Native clients connect their own MTA account to the server HTTPS origin,for example `https://mta.example.org`. API clients use personal bearer tokens with the accounted `/api/ai-jobs/*` endpoints. The reverse proxy forwards these requests unchanged to MTA;MTA binds execution and retained results to the original account,queue,ledger and request key. Raw ACE-Step stays on its private endpoint. Browser clients use normal MTA login and project permissions.

`/api/ai-gateway` is now authenticated GET-only health/model metadata. Raw generation,query_result and v1/audio access are refused because upstream task IDs have no original account/ledger binding. Migrate native Arranger to its MTA-account connection;do not point it at the legacy gateway. Original accounted results remain owner-scoped;unbound historical upstream tasks require isolated operator review. See `LEGACY_EXECUTION_BOUNDARIES_R210.md` for complete IT/EN migration and current limits.

## Configure VM/LXC

Install ACE-Step using `sudo ./install_ace_step.sh --bind local --port 8001` and MTA using `sudo ./install_mta.sh --bind network --port 8080` (check supported flags with `--help`). Configure MTA's root-only `/etc/mta/mta.env` with `MTA_ACE_STEP_URL=http://127.0.0.1:8001`, `MTA_AI_WORKER_ENABLED=true` and a valid `MTA_AI_WORKER_EXECUTABLE`. Restart the MTA service. In Docker/Kubernetes proxy scenarios, open TCP 8080 **only between proxy/Ingress nodes and the VM/LXC**, not from the internet. Ensure ACE-Step's TCP 8001 is NOT reachable from external clients. Public DNS resolves `mta.example.org` to the proxy, not to the VM. Use HTTPS with a trusted certificate; put no shared key in ingress annotations.

## Kubernetes (proxy only, backend VM/LXC)

The YAML files in `deploy/remote-ai/kubernetes/` create a selectorless Service and manual EndpointSlice pointing to the VM/LXC, plus alternative Ingress definitions:

1. Replace `192.0.2.50` in `backend.yaml` with the routable private IP and confirm CNI/ingress pods can connect to it on port 8080. The IP must not be `127.0.0.1` or a Kubernetes Pod address.
2. Create `mta-tls` TLS Secret in namespace `mta-external` using your normal certificate manager or a trusted issuer. Point `mta.example.org` DNS to the Ingress controller's public address.
3. `kubectl apply -f deploy/remote-ai/kubernetes/backend.yaml`
4. Choose exactly ONE ingress: `kubectl apply -f deploy/remote-ai/kubernetes/ingress-nginx.yaml` for community ingress-nginx class `nginx`, OR `kubectl apply -f deploy/remote-ai/kubernetes/ingress-haproxy.yaml` for class `haproxy`. The IngressClass must match the controller installed in your cluster.
5. Restrict traffic to the backend VM with firewall/security groups. Ingress exposes only MTA; it NEVER proxies raw ACE-Step directly.

The NGINX example includes body size and long timeouts. The HAProxy Ingress controller example uses standard Kubernetes Ingress objects; ensure the installed controller has suitable upload limits and read/write timeouts for large audio files, configured via that controller's documented ConfigMap/annotations. Both proxies route all paths unchanged. Size the proxy for the current `app/ai_payload_limits.py` upload/result budgets and the configured inference timeout. The old32MiB metadata gateway limit is not the accounted audio-transfer budget.

## Docker HAProxy without Kubernetes

1. Edit `deploy/remote-ai/docker-haproxy/haproxy.cfg`: replace `mta.example.org` and `192.0.2.50:8080` with the hostname and private MTA target.
2. Install a trusted PEM containing certificate and private key at `deploy/remote-ai/docker-haproxy/certs/mta.pem` (protect private key; do not commit it). Configure DNS and allow ingress TCP 443 to the proxy.
3. `cd deploy/remote-ai/docker-haproxy && docker compose up -d`.
4. Confirm `https://mta.example.org/api/health` returns a successful result, then from a native client test the AI gateway. No public 8001 port is necessary.

## Token lifecycle, resource accounting and billing readiness

Native account approval issues a revocable token for the original user/instance;administrator-issued API tokens also remain owner-scoped. Preserve original request keys and use request-status/request-result/history endpoints for read-only recovery. Accounted registered executions retain their actual measured resources and original ledger/claim. Missing GPU or process-tree evidence is not fabricated from HTTP wall time. Metadata traffic audit remains diagnostic only;it is not an inference invoice. General rights/remote checkpoint/native hardware acceptance remains incomplete.

## Security checklist and diagnostics

- HTTPS termination must preserve `Authorization: Bearer <user token>` through to **MTA**. Never route `/api/ai-gateway/` directly to ACE-Step.
- Restrict MTA backend port 8080 to proxy networks. Never expose ACE-Step port 8001. Separate internal ACE-Step authorization can be configured independently.
- Do not enable `MTA_ALLOW_INSECURE_NO_AUTH` for network-facing MTA; keep standard MTA login enabled.
- Client token errors:401 unauthorized/revoked;403 token/model-policy refusal;404 path not allowed;409 raw gateway operation requires the accounted API;413 body too large;502 metadata upstream connection failure. A browser login session alone does not authorize the gateway API; a dedicated AI token is required.
- GET `https://mta.example.org/api/health` tests the MTA site. Use your configured authenticated API client for GET `/api/ai-gateway/health`;keep credentials out of commands and build logs.
