# MTA Audio Editor - project architecture

Version: 0.2.0-71

## 1. Architectural goals

MTA Audio Editor is a browser-based DAW and MTA interoperability application. The design goals are:

- non-destructive multitrack editing;
- reproducible server-side rendering;
- explicit separation of user projects;
- preservation of original uploaded media;
- conservative handling of proprietary metadata;
- deterministic, testable MTA transformation;
- secure multi-user operation;
- Docker/Kubernetes deployment without privileged runtime requirements;
- auditable CI/CD gates.

The application deliberately separates **editor state**, **rendered media**, **original media**, **proprietary-analysis artifacts**, **authentication state**, and **deployment state**.

## 2. Logical architecture

```text
Browser
  |
  | HTTPS / session cookie / JSON + multipart
  v
FastAPI application
  |
  +-- authentication / authorization / TOTP / SMTP
  +-- project/workspace API
  +-- editing API
  +-- DSP/plugin registry
  +-- MTA codec adapter
  +-- proprietary MTA analyzer
  |
  +--> FFmpeg / FFprobe
  +--> optional Demucs
  |
  v
Persistent data root (/data/projects)
```

### Main source modules

| Module | Responsibility |
|---|---|
| `app/main.py` | HTTP routes, security middleware, page/API orchestration |
| `app/auth.py` | users, sessions, email verification, TOTP, SMTP |
| `app/models.py` | validated Pydantic project/editor data model |
| `app/storage.py` | filesystem confinement, ownership, sharing, archives |
| `app/audio_engine.py` | non-destructive render, synchronization, mix/export |
| `app/plugins.py` | allow-listed DSP schemas/presets/filter construction |
| `app/auto_mix.py` | deterministic reversible mix automation |
| `app/codec.py` | MTA import/export, proprietary media transport integration |
| `app/mta_reverse.py` | byte-level MTA/SYL/XML reverse analysis |
| `app/security.py` | legacy/basic compatibility and security helpers |
| `app/version.py` | project/build identity |

## 3. Request lifecycle

A normal authenticated request traverses:

```text
ASGI/Uvicorn
 -> FastAPI middleware
 -> session/basic-auth lookup
 -> request-integrity check for mutations
 -> upload size check
 -> route authorization
 -> Pydantic validation
 -> storage/audio/codec operation
 -> security response headers
```

Mutating API calls require `X-MTA-Request: 1`. This is an additional same-origin/request-intent control; it does not replace authentication.

## 4. Multi-user authorization model

Persistent users live in `auth.sqlite3`.

Roles:

```text
admin
user
```

Account state:

```text
registered
 -> email confirmed
 -> admin approved/active
 -> optional TOTP enabled
```

Project authorization is independent from role authentication:

```text
owner_user_id
shared_with_user_ids[]
```

A normal user sees:

- owned projects;
- explicitly shared projects.

A collaborator may edit a shared project. Ownership-sensitive operations such as deletion and share management remain restricted to the owner or an administrator.

## 5. Session security

Sessions use high-entropy opaque tokens. Only a hash is stored server-side.

Cookies are:

```text
HttpOnly
SameSite=Lax
Secure when HTTPS / X-Forwarded-Proto=https
```

Password hashing uses PBKDF2-SHA256 with per-password random salt and a high iteration count.

TOTP:

```text
RFC 6238
SHA-1
30-second step
6 digits
window: previous/current/next step
```

TOTP and SMTP secrets are sealed using an application-local persistent secret stored below the data root with restrictive permissions.

## 6. Persistent storage layout

Default root:

```text
/data/projects
```

Global files can include:

```text
auth.sqlite3
.auth-secret
_custom_presets.json
.cache/
```

Each project directory contains:

```text
<project-id>/
  project.json
  audio/
  attachments/
  originals/
  source.mta              # when applicable
  mta-analysis.json       # imported MTA analysis
  generated sidecars      # e.g. reconstructed MIDITK MIDI
```

`originals/` is intentionally separate from working/rendered audio. Project archives and administrator dumps include the original uploaded files.

## 7. Non-destructive editing model

A `Track` references one immutable working source file and one or more `Clip` objects.

Each Clip defines:

```text
source_start_ms
source_end_ms
timeline_start_ms
```

Editing modifies clip ranges and positions rather than rewriting the source.

Track processing pipeline:

```text
source
 -> clip selection/placement
 -> track insert chain
 -> fader
 -> pan
 -> slot merge or stereo summing
```

Master export pipeline:

```text
all rendered tracks
 -> mute/solo resolution
 -> stereo sum
 -> master gain
 -> master insert chain
 -> encoder
```

## 8. MTA output capacity and slot mapping

Editor track count is unrestricted by MTA8/MTA16 capacity.

At MTA export:

```text
MTA8  -> max 8 output slots
MTA16 -> max 16 output slots
```

If project track count exceeds capacity, every track must be assigned exactly once to an output slot. Multiple project tracks mapped to the same slot are rendered and summed before container creation.

This separates creative project structure from device transport limits.

## 9. DSP plugin architecture

Plugins are server-registered. The browser can select:

- plugin type;
- factory preset;
- user preset;
- validated numeric/string parameters.

It cannot send arbitrary FFmpeg filter expressions.

This prevents the UI from becoming a shell/filter-language injection boundary.

Plugin registry categories include:

- parametric EQ;
- 32-band graphical EQ;
- normalization;
- compression;
- limiting;
- delay;
- reverb;
- room/ambience;
- amplification;
- stereo imaging;
- loudness/maximization;
- mastering wizard;
- denoise;
- crackle/click cleanup.

## 10. Auto Mix architecture

Auto Mix is deterministic and reversible.

On enable:

1. capture a snapshot of per-track gain/pan/inserts;
2. capture master gain/inserts;
3. apply type-aware rules for selected style.

On disable:

1. restore the exact snapshot;
2. remove Auto Mix state.

This avoids cumulative drift across repeated toggles.

## 11. MTA interoperability architecture

MTA handling has two cooperating layers.

### Codec layer

`app/codec.py` performs operational import/export:

- creates canonical media using FFmpeg;
- extracts audio streams;
- preserves attachments;
- maps tracks/slots;
- applies/removes proprietary media XOR transport;
- validates generated transport.

### Reverse-analysis layer

`app/mta_reverse.py` performs evidence-oriented parsing:

- EBML/SeekHead/Cues inspection;
- proprietary 984-byte media transport validation;
- attachment extraction fallback;
- ID3v2.3 inspection;
- SYL section parsing;
- 256-byte SYL keystream recovery;
- LYRICS/CHORDS/COLORS decoding;
- MIDITK reconstruction;
- MtxInfoData XML interpretation.

Operational code depends only on demonstrated invariants. Unknown/unverified bytes are preserved rather than synthesized casually.

## 12. Import flow

```text
uploaded .MTA
 -> preserve original
 -> inspect first media Cluster
 -> if proprietary XOR detected:
      create temporary canonical Matroska view
 -> FFprobe canonical view
 -> extract audio tracks
 -> preserve/extract attachments
 -> reverse-analysis original file
 -> populate project model
 -> persist project.json
```

The original uploaded MTA remains available in the project's originals/source data.

## 13. Export flow

```text
project state
 -> validate slot mapping
 -> render every project track
 -> merge tracks assigned to same output slot
 -> create canonical Matroska with streams/attachments
 -> locate first Cluster
 -> apply 984-byte XOR transport through EOF
 -> validate decoded first Cluster
 -> publish .MTA
```

Imported proprietary attachments are preserved where applicable. Native synthesis of metadata follows only the semantics documented in the MTA format appendix.

## 14. Workspace archives

A project archive is a complete portable ZIP:

```text
archive-manifest.json
project/
  project.json
  audio/
  attachments/
  originals/
  source.mta
  analysis/sidecars as present
```

Import creates a new project ID, assigns ownership to the importing user and clears old share relationships.

Administrator full-project dump organizes project directories under user ownership and includes original media. Authentication database and SMTP credentials are deliberately excluded from project dumps.

## 15. Kubernetes architecture

The deployment uses:

```text
Namespace
PVC
Secret
Deployment
Service
optional Ingress
```

Runtime security context uses non-root UID/GID 10001 and pod `fsGroup: 10001` so the application can initialize persistent SQLite/files on compatible CSI/storage implementations.

Probes:

```text
startupProbe  -> /api/health
readinessProbe -> /api/health
livenessProbe  -> /api/health
```

The wizard configures:

- namespace;
- image;
- `imagePullPolicy`;
- PVC size/StorageClass;
- admin bootstrap credentials;
- maximum upload size;
- node selector;
- NGINX/HAProxy Ingress;
- TLS termination/secret.

Ingress upload limit and application `MTA_MAX_UPLOAD_MB` are generated from the same value.

## 16. Backup boundaries

Minimum state for full recovery:

```text
/data/projects
```

This contains project data and authentication state.

Model caches under `.cache` are optional if they can be redownloaded.

Two backup products have different scope:

- **PVC backup/snapshot**: full service recovery including users/auth.
- **administrator project dump**: projects/files/originals only, intentionally excluding credentials.

## 17. Failure domains

Common failure domains are intentionally isolated:

| Domain | Typical failure | Isolation |
|---|---|---|
| Auth DB | invalid/missing bootstrap or permissions | health/logs, PVC |
| Media render | FFmpeg error | project operation only |
| Stem model | download/OOM | plugin operation only |
| SMTP | unavailable server | registration mail notification; account data preserved |
| MTA proprietary parse | malformed attachment | analysis report warning; originals preserved |
| Ingress upload | proxy limit | request rejected before app |
| PVC ownership | DB/project write failure | startup/readiness and logs |

## 18. Observability

The application currently exposes health via `/api/health` and emits server/application logs through stdout/stderr.

Production operators should collect:

- pod restarts;
- readiness failures;
- HTTP 4xx/5xx;
- storage capacity;
- FFmpeg/Demucs process failures;
- SMTP failures;
- authentication events where appropriate.

## 19. Testing strategy

Testing is layered:

1. model/storage unit tests;
2. auth/TOTP/SMTP tests;
3. editing/render tests;
4. proprietary parser tests;
5. MTA media transport tests;
6. workspace/share/archive tests;
7. Kubernetes wizard tests;
8. mobile/static UI regression tests;
9. coverage gate;
10. security/static-analysis gates;
11. container build and smoke test;
12. image vulnerability scan.

## 20. Design constraints and deliberate non-goals

- Browser does not receive direct filesystem paths.
- Browser does not submit arbitrary FFmpeg commands.
- Imported originals are not destructively edited.
- Proprietary metadata is not silently rewritten unless the semantics are documented.
- Project dump is not an account credential backup.
- CI structural validation is not presented as physical-device certification.

See also:

- `docs/MTA_FORMAT_FINAL_SPEC.md`
- `docs/DATA_MODEL.md`
- `docs/API_REFERENCE.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/TESTING_AND_RELEASE.md`
- `docs/SECURE_DEVELOPMENT.md`



## 21. Persistent project lifecycle and stem-separation jobs

Project creation is immediately persistent. The browser asks for a project name before calling `POST /api/projects`; the server creates the project directory and writes `project.json` before returning it.

The editor uses two persistence layers:

1. server-side operations such as audio import, replace, split/ripple, Auto Mix and stem creation save the project synchronously after the operation;
2. purely client-side mixer/metadata changes use a debounced autosave (`PUT /api/projects/{id}`), normally within about 650 ms of the last change.

Before changing project, export/render operations flush pending autosave state.

### Import + Separate workflow

The stem workflow is asynchronous:

```text
choose MP3
 -> choose current/new project
 -> if new: require project name and create persistent project
 -> store MP3 in audio/ and originals/
 -> create Original Mix track
 -> save project
 -> start Demucs worker thread
 -> expose progress through /api/stems/jobs/{id}
 -> append each completed stem
 -> save project after every appended stem
 -> mark job completed
```

The browser polls job status and displays a graphical progress bar, current phase and Cancel action. Cancellation sets a thread-safe event; the Demucs subprocess is terminated and any partial stem tracks from that job are rolled back. The imported original remains preserved.

Only one active stem-separation job is allowed per project.

Job state is runtime state; project/audio state is persistent. A pod restart can therefore interrupt an active AI separation, but it cannot lose the project, the original MP3 or stems already committed before a completed operation.

### Local save and deletion

"Save project locally" downloads the complete `.mta-project.zip` archive. This is separate from workspace persistence: projects already remain stored server-side in the user's workspace.

Deletion removes the complete project directory and is allowed only to the project owner or an administrator. Shared collaborators cannot delete the owner's project.


## Project deletion safety

La cancellazione di un progetto elimina l'intero workspace del progetto, inclusi audio, originali, attachment e file generati; l'interfaccia richiede sempre due conferme consecutive, la seconda esplicitamente irreversibile.



## 22. Timeline/waveform and real-time preview architecture

Track waveform data is persisted in each Track as a normalized peak array plus a source revision. The revision is based on working-source filename, size and mtime. A mismatch schedules an asynchronous waveform job; completion updates `project.json`.

The editor has two vertically synchronized scroll surfaces: the Tracks column and timeline pane. The Tracks column width is a persisted project property. UI rerenders capture and restore Tracks, timeline and mixer scroll offsets.

Preview has two modes:

- **Dynamic**: one audio preview per audible track, preserving clip layout, fader, pan and project tempo/pitch while omitting insert processing for low-latency audition.
- **Render**: server-rendered master including track inserts and master chain. With RealTime metering active, silent per-track rendered previews feed Web Audio analysers while the rendered master remains the audible signal.

RealTime meters use RMS estimates from `AnalyserNode` time-domain buffers and are intentionally separate from the static fader-level indicator.

Global tempo/pitch are persisted as `base_bpm`, target `bpm` and `pitch_semitones`. FFmpeg uses resampling plus chained `atempo` stages to keep pitch shift and time-stretch independent. Export paths use the same project transform.

Project deletion is destructive: storage removes the whole project directory. The UI therefore requires two explicit confirmations before the DELETE request.



## 23. Native desktop architecture

Windows and macOS use a PyInstaller-packaged launcher around the existing FastAPI application and a native `pywebview` window.

Startup sequence:

```text
native executable
 -> resolve per-user application data directory
 -> enable MTA_NATIVE_SINGLE_USER
 -> prepend bundled FFmpeg/FFprobe directory to PATH
 -> start FastAPI/Uvicorn on 127.0.0.1:<ephemeral-port>
 -> wait for /api/health
 -> open native webview
 -> shut down Uvicorn when the native window closes
```

Native single-user mode deliberately bypasses the account database and suppresses login, registration, account administration, SMTP/TOTP, admin-user endpoints and project-sharing endpoints. Internally a synthetic local principal is used only to reuse the project authorization code paths.

The native launcher supports an internal `--demucs-worker` mode so a frozen PyInstaller executable can spawn Demucs separation jobs without requiring an external Python interpreter.

GitHub Actions builds both desktop installers only after quality and security jobs pass. Each packaged executable is exercised with `--native-smoke` before installer creation. Tag builds publish the generated Windows Setup executable and macOS DMG to the GitHub Release.



## 23. Native desktop editions

The Windows and macOS editions reuse the same application core but run with `MTA_NATIVE_SINGLE_USER=true`. The desktop launcher starts Uvicorn on an ephemeral loopback-only port and opens it inside a native `pywebview` window. Native mode injects a synthetic local administrator principal and blocks login, logout, account, registration, password-reset, SMTP/admin-user and project-sharing routes.

The native application therefore keeps project authorization simple while preserving the exact editor/storage/audio/MTA pipeline used by the server edition. Projects are local to the OS user profile. No listening socket is exposed outside `127.0.0.1`.

PyInstaller bundles Python, application modules, templates/static assets, documentation, FFmpeg/FFprobe, Demucs, Torch and Torchaudio. The desktop launcher contains a dedicated frozen-process Demucs worker mode so stem separation does not depend on a system Python interpreter.

GitHub Actions builds:

```text
Windows x64        -> Inno Setup .exe
macOS Intel x64    -> .app + .dmg
macOS Apple Silicon -> .app + .dmg
```

Every native runner performs an executable-level single-user smoke test before installer creation. Tag workflows publish installer artifacts and SHA-256 sidecars to the GitHub Release.
