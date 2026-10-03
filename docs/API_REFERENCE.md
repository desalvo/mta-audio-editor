# HTTP/API reference

All non-public API routes require authentication.

Mutating `/api/*` requests require:

```text
X-MTA-Request: 1
```

unless explicitly public.

## Public

```text
GET  /api/health
GET  /api/about
GET  /login
POST /login
GET  /register
POST /register
GET  /verify-email
POST /resend-verification
GET/POST /forgot-password
GET/POST /reset-password
GET  /docs/user
GET  /docs/user/en
GET  /docs/pdf/user
```

## Session/account

```text
GET    /api/session
GET    /api/account
PATCH  /api/account
POST   /api/account/password
POST   /api/account/totp/begin
GET    /api/account/totp/qr
POST   /api/account/totp/enable
POST   /api/account/totp/disable
GET    /logout
```

## Administration

```text
GET    /admin/users
GET    /api/admin/users
PATCH  /api/admin/users/{user_id}
DELETE /api/admin/users/{user_id}
GET    /api/admin/smtp
PUT    /api/admin/smtp
POST   /api/admin/smtp/test
GET    /api/admin/projects-dump
```

Admin-only web/PDF documentation routes remain protected.

## Projects

```text
GET    /api/projects
POST   /api/projects
GET    /api/projects/{pid}
PUT    /api/projects/{pid}
DELETE /api/projects/{pid}
```

## Sharing

```text
GET    /api/projects/{pid}/shares
POST   /api/projects/{pid}/shares
DELETE /api/projects/{pid}/shares/{user_id}
```

## Project files and complete archives

```text
GET    /api/projects/{pid}/files
POST   /api/projects/{pid}/files/upload
GET    /api/projects/{pid}/files/{category}/{filename}
DELETE /api/projects/{pid}/files/{category}/{filename}
GET    /api/projects/{pid}/archive
POST   /api/project-archives/import
```

## Audio/project operations

The application provides routes for:

- track upload/add/replace;
- manual move;
- auto alignment;
- range delete/ripple;
- full-song delete;
- Auto Mix;
- plugin/preset management (including factory parameter values used by the live editor);
- master preview;
- individual track export;
- WAV/MP3/FLAC export;
- MTA export;
- stem separation.

Refer to route definitions in `app/main.py` as the executable source of truth.


## Configured project export and MTA profiles

```text
GET  /api/projects/{pid}/export-plan?profile=<profile>
POST /api/projects/{pid}/configured-export
POST /api/projects/{pid}/configured-export-jobs
POST /api/projects/{pid}/export-mta
```

`export-plan` returns target capacity, project track count, suggested slot assignments and the resolved device profile. Supported profile identifiers include:

```text
auto
merish5_xynthia2
bbeat_divo
mlive_mta16_default
merish5_plus_mta16
generic
```

Configured MTA export accepts `mta_device_profile` plus an optional explicit `slots[]` mapping. MTA8 device profiles preserve physical Click/Melody positions; the corpus-derived MTA16 default proposes Click 1 / Melody 9. Silent intermediate streams may be generated to preserve the requested physical position. Explicit mappings remain authoritative when supplied.

For native desktop mode, `output_path` may be provided by the native file chooser. Web/mobile clients normally receive a download artifact instead.

## MTA analysis

Routes include analysis/report access, binary diff support and verified MIDITK sidecar download where available.

The analysis API reports evidence and validation state; it should not be treated as an authorization boundary.

## Error conventions

Typical HTTP results:

```text
200/303 success
400 invalid user/project/media input
401 unauthenticated API request
403 authenticated but forbidden / missing mutation integrity header
404 inaccessible or absent project/resource
413 request above configured upload limit
422 Pydantic/FastAPI validation failure
```

For project authorization, an inaccessible project may deliberately return 404 to avoid leaking existence to unrelated users.



## Asynchronous stem separation

```text
POST /api/stems/jobs
GET  /api/stems/jobs/{job_id}
POST /api/stems/jobs/{job_id}/cancel
```

`POST /api/stems/jobs` accepts an MP3 multipart file and query parameters:

```text
project_id            existing destination, optional
project_title         required by UI for a new project
target                MTA8 | MTA16
model                 htdemucs | htdemucs_ft | htdemucs_6s
keep_original_track   true | false
```

The response includes both the already-persisted project and a job descriptor.

Job states:

```text
queued
running
cancelling
completed
failed
cancelled
```

The job descriptor includes `progress` (0..100), `message`, model, source filename and optional error text.

The older synchronous `POST /api/stems/split` endpoint is retained for backward compatibility.



## Waveform and preview

```text
POST /api/projects/{pid}/tracks/{track_id}/waveform-jobs
GET  /api/media-jobs/{job_id}
GET  /api/projects/{pid}/preview-track/{track_id}?render=false|true
GET  /api/projects/{pid}/preview-mix
```

`waveform-jobs` regenerates and persists normalized waveform peaks when the source revision changes. `preview-track` renders clip layout, fader/pan and project tempo/pitch; `render=true` additionally applies the track insert chain. `preview-mix` renders the complete master chain and is used by the transport when Render mode is enabled.

## Documentation downloads

```text
GET /docs/pdf/user
GET /docs/pdf/user/en
GET /docs/pdf/admin
GET /docs/pdf/admin/en
```

The legacy `/docs/pdf/user` and `/docs/pdf/admin` endpoints serve the Italian manuals; the `/en` variants serve the English manuals.


## Track MTA slot preference

`Track.mta_slot` is optional. `null` means automatic/profile-driven placement; an integer stores the preferred physical output slot. Export-plan suggestions honor valid explicit track slots, and the UI persists slot choices when the user confirms an MTA mapping.

## Plugin manifest parameter values

`GET /api/plugins` returns `factory_params` alongside preset names and schemas. Every factory preset exposes a schema-valid parameter dictionary so the editor can update knobs/numeric controls immediately when preset selection changes.
