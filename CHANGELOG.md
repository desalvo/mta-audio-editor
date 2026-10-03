## 0.2.0-70

- CI: suppress Ruff/Bandit S310 on both `urllib.request.Request` construction and `urlopen`, only after strict HTTPS/provider-host validation in `_validate_oauth_endpoint`.
- Keeps the OAuth endpoint allowlist, HTTPS-only policy, no embedded credentials, and port 443-only validation introduced in 0.2.0-69.

## 0.2.0-70

- Security/CI fix for social OAuth HTTP calls: endpoints are now restricted to HTTPS and to the explicit Google, GitHub and Facebook provider hosts before any network request.
- Ruff S310 is suppressed only on the validated `urlopen` call, with regression coverage for rejected schemes, credentials, ports and untrusted hosts.

## 0.2.0-68

- Added optional OAuth 2.0 login/registration with Google, Facebook and GitHub; all providers are disabled by default.
- Social registrations trust only a provider-supplied verified email, skip local email verification, and remain inactive until administrator approval.
- Added signed, short-lived OAuth state bound to an HttpOnly browser cookie and persistent provider/subject identity mapping.
- Existing local accounts are never auto-linked solely by matching email.
- New registrations notify administrators when SMTP is configured; administrator approval sends the activation email to the user.
- Added Docker/Kubernetes defaults and `docs/SOCIAL_LOGIN.md` with provider callback and enablement instructions.

## 0.2.0-68

- Auto-save enabled by default, configurable in desktop Settings; manual Save remains available.
- Session Undo/Redo with standard shortcuts.
- Timeline Cut/Copy/Paste/Remove for selected ranges/tracks.
- Fixed selected-track checkbox lookup.

## 0.2.0-68

- Fixed desktop-native save-location chooser by waiting for the pywebview JS bridge instead of silently returning while the bridge is still initializing.
- Import & Separate now requires and opens a native save destination chooser when the destination is a new project.
- Renamed Native settings to Settings and made native detection/session/bridge readiness consistent.
- Grouped Import MTA, Import Audio, Import & Separate, Tracks, Plugins and Mixer into a dedicated collapsed-by-default EDIT / IMPORT / MIX sidebar section.
- Tracks, Plugins and Mixer now perform explicit navigation/focus actions and report when a project/track is required.

## 0.2.0-68

- Portato a 1024 MB (1 GiB) il limite predefinito di import/upload per server, Docker e Kubernetes.
- `MTA_MAX_UPLOAD_MB` resta configurabile in Docker; il wizard Kubernetes configura coerentemente applicazione e Ingress NGINX/HAProxy fino a 10240 MB.
- Le app desktop native hanno ora **Native settings** con limite import/upload configurabile 1–10240 MB, persistente e applicato immediatamente senza riavvio.
- Il limite continua a essere verificato sia sul `Content-Length` sia durante la copia streaming del file, evitando di caricare l’intero upload in RAM.

## 0.2.0-68

- Corretto il secondo errore Android rilevato nel run GitHub Actions 37057175276: il progetto usa dipendenze AndroidX ma non abilitava `android.useAndroidX`.
- Aggiunto `mobile/android/gradle.properties` con AndroidX abilitato e Jetifier disabilitato, dato che le dipendenze del progetto sono già AndroidX.
- Aggiunto test regressivo per impedire la rimozione accidentale della configurazione AndroidX.

## 0.2.0-68

- Il menu contestuale di una traccia include anche `Rimuovi`, per eliminare la traccia selezionata dal progetto.

- Aggiunti input numerici sincronizzati con gli slider del volume per tracce, Inspector, Mixer e Master; valori ammessi da -60 a +12 dB con autosave.


- `Import Audio` ora avvia automaticamente l'import immediatamente dopo la scelta del file, senza richiedere un secondo click.
- `Delete tracks` ora elimina realmente le tracce selezionate dal progetto; non richiede più una selezione temporale.
- `Delete song segment` mantiene invece il comportamento di cancellazione intervallo/ripple sulla timeline.

- Added full multi-user authentication with a responsive photographic login based on the approved mockup.
- Added self-registration with mandatory email confirmation and administrator approval before activation.
- Added `admin`/`user` roles, admin-only user management, activation/deactivation, role changes and deletion safeguards that preserve at least one active administrator.
- Added optional RFC 6238 TOTP with in-app secret generation and QR-code enrollment.
- Added user profile management, email-change reverification/reapproval, password change and email password reset.
- Added SMTP/STARTTLS/SMTPS configuration with optional credentials, connection test, confirmation mail and activation notifications to all active administrators with confirmed email addresses.
- Added persistent SQLite authentication/session data on the application volume and HttpOnly/SameSite application sessions while keeping HTTP Basic only for operational compatibility.
- Updated Docker Compose and Kubernetes bootstrap configuration to include the administrator email.
- Preserved the previous Python 3.14/Trixie, CPU-only PyTorch, CI security, Kubernetes TLS and MTA reverse-engineering work.

# Changelog

## 0.2.0-13

- Fixed Ruff 0.16.9 CI failures in the standalone Kubernetes wizard: removed an unused import and documented narrow S310/S606 suppressions for the hard-coded HTTPS self-update URL and intentional shell-free self-restart.
- Kept the Python 3.14 production/CI baseline while making dependency resolution deterministic on GitHub-hosted runners.
- Pinned Pydantic to 2.12.5 (pydantic-core 2.41.5), a stable Python 3.14-compatible pair, after the 2.13.5/core 2.46.5 combination intermittently failed to resolve in the Quality job.
- Added a Dependabot guard against Pydantic 2.13.x/2.14.x until the CPython 3.14 production gate is deterministic.
- Moved the production and CI baseline from Python 3.11 to Python 3.14, absorbing the previous Docker Dependabot PR.
- Updated NumPy to 2.5.3 and aligned the dependency policy with the Python 3.14 baseline, absorbing the remaining grouped Python dependency PR intent.
- Split Kubernetes assets into Namespace, PVC, Deployment and Service resources and added Kustomize base/overlays.
- Added NGINX Ingress and HAProxy Ingress examples.
- Added a standalone standard-library Kubernetes manifest wizard with self-update, automatic restart after update, persistent last-used values, nodeSelector support, StorageClass selection and local Kustomization output.
- Added wizard generation tests and security notes for locally persisted/generated credentials.


## 0.2.0-10

- Resolved the two open Dependabot proposals without changing the 0.2.x Python 3.11 support baseline.
- Incorporated compatible dependency updates from PR #4: Demucs 4.1.0, pytest 9.1.1, pytest-cov 7.1.0, Ruff 0.16.9, Bandit 1.9.4, pip-audit 2.10.1 and WeasyPrint 70.0.
- Kept NumPy at 2.4.6 because NumPy 2.5.x requires Python >=3.12.
- Kept the production base image on python:3.11-slim-bookworm instead of PR #1's Python 3.14 proposal.
- Added Dependabot ignore policy for Python 3.12+ Docker bases and NumPy 2.5+ while the 0.2.x compatibility policy remains Python 3.11.
- Fixed Gitleaks pull-request scans by checking out full Git history in the security job.
- Updated the Docker stem-plugin smoke import for Demucs 4.1, which no longer requires torchaudio for inference.
- Retained setuptools 84.0.0 / wheel 0.48.0 runtime hardening for the previous Trivy findings.

## 0.2.0-9

- Fixed the current Trivy production-image gate by upgrading runtime packaging tooling to `setuptools==84.0.0` and `wheel==0.48.0`.
- `setuptools 84.0.0` vendors `jaraco.context 6.1.0` and `wheel 0.46.3`, eliminating CVE-2026-23949 and CVE-2026-24049 reported against the base image's `setuptools 79.0.1`.
- Added a Docker build-time import smoke test for core runtime modules and optional Torch/Torchaudio stem-separation modules.
- Retained all 0.2.0-8 MTA reverse-engineering, security, documentation and CI improvements.

## 0.2.0-8

- Consolidated the GitHub Actions fixes for Python 3.11 and current action tags, including Trivy `v0.36.0`, CodeQL v4 and NumPy 2.4.6.
- Hardened XML parsing with `defusedxml` and replaced silent exception swallowing with explicit logged fallbacks.
- Upgraded proprietary MTA analysis with a corpus-verified 256-byte shared keystream recovered from COLORS.
- Decoded COLORS normal records as four decimal centisecond digits plus three decimal progressive highlight-position digits and minute carry; special sentinel values remain read-only/undocumented.
- Added corpus-verified LYRICS/CHORDS decoding with monotonic minute/centisecond timing and XOR-0x30 text/chord recovery.
- Added MIDITK decoding to byte-exact Standard MIDI plus MIDI header, PPQ, track-length, tempo and Marker meta-event analysis.
- Added `docs/MTA_FORMAT_RESEARCH.md` and `docs/PROJECT_ARCHITECTURE.md` and updated online/PDF manuals with current compatibility boundaries.
- Retained conservative write policy: unknown fields and proprietary writer semantics are preserved, not synthesized, until hardware round-trip validation is complete.

## 0.2.0-6

- Fixed current GitHub Actions references and Python 3.11 compatibility.
- Added `defusedxml` for untrusted XML parsing and explicit exception logging/fallbacks.
- Corrected Python 3.11-incompatible test syntax reported by Ruff.

## 0.2.0-5

- Added verified structural parsing for stock M-Live SYL/XML attachments.
- Added read-only LYRICS/CHORDS decoding and initial COLORS keystream/timing analysis.
- Added MtxInfoData parsing and conservative EBML FileData attachment fallback.

## 0.2.0-4

- Added Delay, Lexicon-style Reverb, Room/Ambience, 32-band Graphic EQ, Amplify, Stereo Imager, Maximizer/Loudness, Mastering Wizard, De-Noise and Crackling Cleaner.
- Added factory presets and persistent validated user presets for every insert processor.
- Added parameter editor and reversible Auto Mix with Balanced/Studio/Live/Gentle profiles.

## 0.2.0-3

- Removed the MTA8/MTA16 slot limit from the editing/mixing workspace.
- Added explicit MTA output-slot mapping and many-to-one track merge during export.
- Added independent WAV/MP3/FLAC track export and FLAC master export.
- Added the first Matroska/SYL reverse-analysis reports and binary diff tooling.

## 0.2.0-2

- Added the photographic DAW interface, mixer and master preview.
- Added direct MP3/WAV track import/replacement and Demucs stem separation.
- Added per-track/master insert chains and WAV/MP3 master export.

## 0.2.0-1

- Added production CI/CD, CodeQL, Dependabot, SBOM/provenance and security gates.
- Added default-on authentication, request-integrity checks, upload/path hardening and non-root container deployment.
- Added integrated user/admin online and PDF documentation.

## 0.2.0

- Added non-destructive clip editing, arbitrary range deletion, ripple editing, track import/replace/sync, history/timeline events and initial MTA import/export preservation model.

## 0.1.0

- Initial FastAPI/FFmpeg MTA8/MTA16 web editor prototype.

## 0.2.0-68

- Kubernetes wizard: HAProxy ingress now always emits `kubernetes.io/ingress.class: haproxy` in addition to `spec.ingressClassName: haproxy`.
- Reverse-engineering notes: confirmed the 181392 ns Matroska timecode scale, 40 MP3 frames per Cue interval, exact 320 kbit/s frame/SimpleBlock sizing, and frame-major per-track interleaving evidence.
