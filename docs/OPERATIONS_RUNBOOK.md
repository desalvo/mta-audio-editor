# Operations runbook

## Startup prerequisites

Persistent `/data/projects` must be writable by runtime UID/GID 10001 or by the pod `fsGroup`.

Bootstrap admin creation requires, on an empty auth database:

```text
MTA_ADMIN_USERNAME
MTA_ADMIN_PASSWORD
MTA_ADMIN_EMAIL
```

If the database already contains users, changing those environment variables does not replace existing accounts.

## Kubernetes readiness triage

If a pod never becomes Ready:

```bash
kubectl -n <ns> get pod
kubectl -n <ns> describe pod <pod>
kubectl -n <ns> logs <pod>
kubectl -n <ns> logs <pod> --previous
```

Check in this order:

1. `CreateContainerConfigError` from missing Secret keys.
2. PVC mount errors.
3. permission errors writing `/data/projects`.
4. startup probe failures.
5. missing FFmpeg/runtime dependency.
6. application traceback.

Current generated Deployment uses:

```yaml
securityContext:
  fsGroup: 10001
  fsGroupChangePolicy: OnRootMismatch
```

and makes the bootstrap email Secret reference optional for upgrade compatibility, while the wizard itself writes the email key in newly generated Secrets.

## Upload limits

Default is 150 MB.

The Kubernetes wizard writes the same chosen size to:

```text
MTA_MAX_UPLOAD_MB
NGINX proxy-body-size
or HAProxy proxy-body-size
```

Use:

```bash
python3 scripts/k8s-wizard.py --max-upload-mb 300
```

when a larger value is required.

## Image pull behavior

Wizard option:

```text
--image-pull-policy Always
--image-pull-policy IfNotPresent
--image-pull-policy Never
```

`IfNotPresent` is the default.

## SMTP troubleshooting

From the admin panel configure host, port and one of:

```text
none
STARTTLS
SMTPS
```

Authentication credentials are optional.

Use the built-in connection test. If verification mails are not delivered, check server logs and ensure `MTA_PUBLIC_URL` is correct behind an Ingress/reverse proxy.

## Backup

For complete application recovery back up the PVC/data root.

Administrator project dumps are for project portability/audit and intentionally exclude credentials.

Recommended backup procedure:

1. quiesce writes or take a CSI snapshot;
2. snapshot/copy `/data/projects`;
3. verify archive integrity;
4. periodically restore into an isolated environment.

## Restore

Restore the data root with ownership/permissions compatible with UID/GID 10001. Start one pod first and verify:

```text
/api/health
login
project list
one project render/export
```

before scaling.

## Capacity

Disk consumers:

- originals;
- working audio;
- project archives/exports;
- Demucs/Torch cache;
- temporary render data during active operations.

CPU/RAM spikes mainly come from FFmpeg filtering/encoding and Demucs.

## Upgrade procedure

1. back up PVC;
2. generate/review updated manifests;
3. confirm Secret still includes expected keys;
4. apply manifests;
5. rollout restart;
6. wait for readiness;
7. verify login/admin/project access;
8. run one media preview and one MTA export.

## Logs to retain

At minimum:

- Uvicorn/application logs;
- Kubernetes events;
- Ingress logs;
- CI/CD build logs.

Do not log passwords, TOTP secrets, SMTP passwords or session tokens.



## Stem-separation operations

Demucs runs as a child process of the application and can be CPU/RAM intensive. The UI exposes live progress and cancellation.

Operational notes:

- the MP3 and project are persisted before separation starts;
- only one active stem job is accepted per project;
- cancellation terminates the Demucs process and rolls back partial stems;
- a pod restart interrupts an in-flight job because the job controller is in-memory;
- the underlying project and original MP3 remain safe on the PVC.

For production AI workloads, size CPU/RAM requests according to the selected Demucs model and song duration.

## Scoped Demucs model access

Runtime model downloads use revocable `models:read` bearer tokens issued by `POST /api/models/token`. Desktop native deployments can supply the token through `MTA_MODEL_ACCESS_TOKEN`. CI does not reuse runtime credentials: optional bundled baseline assets are read from the GitHub `demucs-models` release, with runtime authenticated bootstrap as fallback.
