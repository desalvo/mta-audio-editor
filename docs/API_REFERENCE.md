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
- plugin/preset management;
- master preview;
- individual track export;
- WAV/MP3/FLAC export;
- MTA export;
- stem separation.

Refer to route definitions in `app/main.py` as the executable source of truth.

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
