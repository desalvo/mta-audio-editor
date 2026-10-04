## 0.2.0-106

- Fixed Android mobile compilation by explicitly enabling BuildConfig generation for the application module.
- Fixed iOS 15 compatibility by avoiding Locale.Language APIs that require iOS 16.
- Fixed Core ML local-stem model selection by carrying modelId through the synchronous separation path.
- Made Core ML metadata, integer min/max and regular-expression options explicit to avoid Swift type-inference failures in Xcode release builds.
- Added mobile compiler regression checks for the Android and iOS fixes observed in GitHub Actions run #67.

## 0.2.0-105

- Added centralized, periodically synchronized Demucs model catalogue with official Demucs families and manifest-provided mobile/native artifacts.
- Added server model blacklist with managed-storage deletion and web/mobile/native visibility filtering.
- Added server administration UI for model update/blacklist management.
- Added local model management hooks for desktop, iOS/iPadOS, and Android (download/update/delete).
- Native/mobile clients download missing models on demand for splitting.

## 0.2.0-105

- Automatic periodic Demucs mobile-model refresh in Docker/Kubernetes with HTTPS manifest, SHA-256 verification and atomic replacement.
- iPhone/iPad model refresh is periodic and Wi-Fi-only by default, configurable in Options.
- Android receives equivalent periodic ONNX model provisioning, Wi-Fi-only by default.
- Added New project directly inside PROJECT / FILE.

## 0.2.0-105

- Fixed native macOS project destination dialogs: pywebview now uses a valid ZIP filter while preserving the .mta-project.zip extension.
- Prevented accidental utility-modal dismissal when selecting/editing the project name.
- Reworked non-Render playback buffering to use short adaptive pre-roll rather than canplaythrough for every track.
- Reworked multi-track drift correction to use smooth playback-rate nudging and only rare hard seeks.
- Mixer volume, pan, mute and solo are applied immediately in WebAudio and no longer depend on buffering.

## 0.2.0-97

- Added native on-device stem separation for iPhone/iPad using Core ML-compatible Demucs models.
- Added Auto / Local / Server mobile execution modes with automatic server fallback.
- Added authenticated model provisioning and on-device model compilation/cache.
- Added chunked 44.1 kHz stereo inference with overlap-add and WAV stem import into the project.
- Added conservative device-aware Auto stem recommendations and a 12-minute local safety limit.
- Added `scripts/export_demucs_coreml.py` documenting/exporting the expected Core ML model contract.

## 0.2.0-96

- Added configurable stem count: Auto, 2, 4, 6, or 8.
- Added 2-stem Demucs mode (vocals/accompaniment), standard 4-stem mode, and 6-stem extended mode.
- 8-stem mode is exposed only through a compatible backend model configured with `MTA_DEMUCS_8_MODEL`; no synthetic/duplicate stems are generated.
- Persisted the preferred stem count in the application and reused it for full-song and single-track separation.
- Documented identical iPhone/iPad controls; the current mobile build delegates heavy Demucs processing to the server.

## 0.2.0-95

- Fixed GitHub Actions documentation regression test to validate the current bilingual cover assets.
- Added meaningful audio-engine regression tests for media duration, project duration, clip initialization, track shifting and metronome WAV generation.
- Restored CI coverage above the 70% production gate without lowering the configured threshold.
- Updated the production-image fallback version to 0.2.0-95.

## 0.2.0-93

- README.md is now the primary English README; README_IT.md contains the Italian version.
- Added direct README links to user/admin manuals, IT/EN brochures and complete IT/EN MTA format specification PDFs.
- Expanded both product brochures to two pages with operating modes, limits, server/mobile behavior, MTA limits and resource considerations.
- Added full detailed MTA format specification PDFs in Italian and English.

## 0.2.0-92

- Updated documentation cover pages to use the approved mockup-style artwork for IT/EN user and administrator manuals.
- Regenerated the documentation package with refreshed cover assets and updated version/build information.

## 0.2.0-81

- Added unrestricted **Multitrack DAW** project format alongside MTA8/MTA16.
- DAW projects can export WAV/MP3/FLAC directly and choose MTA8 or MTA16 only when an MTA output is requested.
- Selecting a track no longer causes waveform validation/recalculation; persisted waveforms are validated once per project and recomputed only when missing or explicitly invalidated.
- Plugin numeric parameter boxes commit on Enter or focus loss; knobs commit on release/change.
- Removed redundant static volume bars from mixer channels and enlarged the faders.
- Regenerated real-UI documentation screenshots and corrected screenshot text artifacts.
- Reworked PDF covers with an artistic professional DAW photograph behind the existing application data plate and a large application title/logo.

## 0.2.0-81

- Completely expanded the integrated **User Manual** in Italian and English with end-to-end workflows, screenshots, diagrams, examples, troubleshooting, glossary, MTA profiles, synchronized playback and live mixer behavior.
- Expanded the **Administrator Manual** in Italian and English with architecture, deployment, security, storage/backup, audio pipeline, desktop/mobile clients, MTA format, observability, upgrades and CI/CD.
- Rebuilt all four documentation PDFs with a photographic full-page cover, application logo, version/build/creator/license/repository plate and supported-platform badges.
- Added PDF pagination safeguards and verified the generated manuals for orphan headings.
- Consolidated the bilingual MTA format specification with container, media transport, MP3/SimpleBlock, Cluster/Cues/SeekHead, Xing/Info, CRC, SYL/LYRICS/CHORDS/COLORS/MIDITK, MtxInfoData, NoteOn, PreCntUSec, Click/Melody profiles, reader/writer algorithms and validation invariants.
- Updated format documentation to present the MTA specification as corpus-validated technical documentation without describing it as reverse engineering.
- Mobile Android and iOS/iPadOS clients now use the built-in service automatically on first launch, never prompt for a server URL during installation/first run, and never display the built-in default address. A custom URL can be set later in Server settings and may be displayed/edited because it is user-configured.
- Added documentation regression coverage for bilingual manuals, hidden default mobile URL and format-document wording.

## 0.2.0-77

- Added transport **Torna all'inizio** control.
- Dynamic playback now buffers every track before starting, starts all tracks together and continuously corrects decoder drift against a shared transport clock.
- Added visible buffering/synchronization status before Play.
- Render playback now keeps a dedicated master transport clock, restoring Follow during Render and across seamless rendered-master refreshes.
- Added persistent MTA device profiles: Merish5/Xynthia2, B.Beat/DIVO family, Merish5+ PLUS MTA16 and Generic.
- MTA8 export physically pads missing streams with silence when needed so Click/Melody stay at the documented stream positions.
- Merish5/Xynthia2 profile uses Melody 7 / Click 8; B.Beat/DIVO family uses Click 7 / Melody 8.
- MTA16 does not invent a universal Click/Melody position; the Merish5+ PLUS profile requires explicit mapping when Click/Melody are present.
- Imported MTA8 files infer the device profile when the Click/Melody order is unambiguous.

## 0.2.0-76

- Volume, pan, mute/solo and FX chain state now update while Play remains active.
- Track FX changes hot-swap the affected rendered preview at the current cursor; Render mode automatically refreshes the master.
- Master fader is applied relative to the rendered baseline, avoiding double gain.
- Fixed VU meters with Render enabled: analyser paths keep the actual audio level and only the monitor destination is muted.
- MTA import no longer guesses Click/Melody solely from slots 7/8; explicit metadata and track names take precedence.
- Documented M-Live device-profile difference for Click/Melody ordering.

## 0.2.0-75

- Native MTA import now asks where to save the project before the import starts; cancelling the save dialog cancels the import.
- Native project file bindings are persisted across application restarts and are displayed in **Info progetto**.
- Added **Info progetto** under Project / File with name, project ID, home/workspace, location, type, duration, track count, artist, BPM, key and autosave state.
- Mute/solo now update the active WebAudio graph immediately during playback. All tracks stay instantiated and audibility is controlled by gain, so unmute/unsolo no longer requires Stop/Play.
- Rendered-master preview automatically refreshes after live mute/solo changes and refreshes on Resume when changed while paused.
- Includes the 0.2.0-74 macOS WKWebView/pywebview CSP fix (`unsafe-eval` only in native single-user mode).

## 0.2.0-73

- CI: remove the stale unused `revision` assignment in the waveform import fallback so Ruff F841 passes without suppressing the rule.

## 0.2.0-73

- CI: suppress Ruff/Bandit S310 on both `urllib.request.Request` construction and `urlopen`, only after strict HTTPS/provider-host validation in `_validate_oauth_endpoint`.
- Keeps the OAuth endpoint allowlist, HTTPS-only policy, no embedded credentials, and port 443-only validation introduced in 0.2.0-69.


## 0.2.0-73
- Waveform cache resa esplicitamente persistente e validata all'apertura: i picchi salvati nel progetto vengono mostrati subito e la revision server-side rigenera automaticamente solo waveform mancanti o obsolete, salvando il risultato nel progetto.
- La revisione waveform generata durante import/metronomo usa ora la stessa firma track-aware (sorgente + insert) usata per la validazione successiva.
- Il Play/Preview resta indipendente dalla disponibilità o dal calcolo delle waveform.
- Rimosso il pulsante Record dalla transport, non essendo associato ad alcuna funzione di registrazione.
- Aggiunti Mute all / Unmute all, Solo all / Unsolo all e Bypass all FX / Enable all FX per tutti gli insert di traccia e master. Il cambio globale degli FX invalida e rigenera le waveform delle tracce interessate.

## 0.2.0-73

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

- Workspace dedicato per utente con proprietà dei progetti e visibilità dei soli progetti propri/condivisi.
- Condivisione progetto verso altri utenti attivi e confermati; i collaboratori possono modificare, mentre gestione condivisioni ed eliminazione restano al proprietario/admin.
- Gestione file progetto con elenco, download, upload di file originali aggiuntivi e cancellazione sicura dei file non referenziati.
- Conservazione automatica degli upload originali in `originals/`, inclusi audio importati, sostituzioni, sorgenti MTA e input MP3 dello stem splitter.
- Export/import completo di un progetto tramite archivio `.mta-project.zip`, con riassegnazione al nuovo proprietario e reset delle condivisioni all'import.
- Dump amministrativo completo di tutti i progetti di tutti gli utenti, organizzato per proprietario e comprensivo dei file originari.
- Limite upload predefinito portato a 150 MB; wizard Kubernetes configurabile con `--max-upload-mb` e annotazioni Ingress NGINX/HAProxy coerenti.
- Overlay Kubernetes e Docker Compose aggiornati al nuovo limite.
- Migrazione automatica dei progetti legacy senza proprietario verso il primo amministratore persistente che apre il workspace.

# MTA Audio Editor 0.2.0-68

## Multi-user authentication and administration

This release replaces the browser-facing single-admin login flow with application-managed users and a responsive photographic login faithful to the approved visual concept. Users can self-register, must confirm a mandatory email address, and remain inactive until approved by an administrator. Administrators can manage users and roles, while safeguards prevent accidental removal of the final active administrator.

Users can optionally enable TOTP from their profile. MTA Audio Editor generates the TOTP secret and QR code internally. Administrators can configure SMTP, STARTTLS or SMTPS with optional credentials, test connectivity, and use the mail service for address verification and activation notifications. All active administrators with confirmed email addresses are notified when an account is activated.

Authentication state is persisted on the application data volume, browser sessions use HttpOnly/SameSite cookies, and password/email changes invalidate or re-gate access as appropriate. Docker Compose and the Kubernetes manifest wizard now include the bootstrap administrator email.

The release also retains the current Python 3.14 / Debian Trixie container baseline, CPU-only PyTorch multiarch strategy, GitHub Actions security gates, Kubernetes HAProxy TLS behavior, and accumulated MTA reverse-engineering work.

# MTA Audio Editor 0.2.0-13

## Python 3.14 and Kubernetes/Kustomize release

This release supersedes the two previously open Dependabot proposals by adopting the Python 3.14 container baseline and the compatible dependency set instead of suppressing those updates.

- Production and CI baseline: `python:3.14-slim-bookworm`.
- NumPy updated to 2.5.3.
- Demucs remains 4.1.0 and the production image validates the Python 3.14 stem stack.
- The Docker and Python dependency PR intents are therefore incorporated into mainline package contents.
- Gitleaks pull-request scanning keeps full Git history.


## GitHub Actions reliability fix

The follow-up Quality run also exposed three Ruff 0.16.9 findings in the Kubernetes wizard. The unused import was removed; the two security rules are suppressed only at the exact intentional operations (`urlopen` against the hard-coded HTTPS GitHub raw URL and `os.execv` for shell-free self-restart), with inline rationale.

The Python 3.14 baseline remains enabled. The Quality job exposed an intermittent resolver failure for `pydantic==2.13.5`, which requires `pydantic-core==2.46.5`. The Security job in the same workflow could resolve it while the Quality job could not. This release pins `pydantic==2.12.5`, whose `pydantic-core==2.41.5` dependency has established CPython 3.14 wheels, and prevents Dependabot from immediately reopening the unstable 2.13/2.14 upgrade.

## Kubernetes

Kubernetes resources are now split under `k8s/base` into Namespace, PVC, Deployment and Service, with an example Secret kept outside the default Kustomization. NGINX and HAProxy Ingress examples are supplied as independent Kustomize overlays.

A new `scripts/k8s-wizard.py` is downloadable directly from the GitHub raw URL and uses only the Python standard library. It asks for initial administrator username/password, PVC StorageClass, namespace and nodeSelector, remembers the last values in a mode-0600 configuration file, can optionally generate NGINX/HAProxy Ingress, and creates a local Kustomization. On startup it checks GitHub for a strictly newer wizard version; after an atomic self-update it automatically restarts itself.

The generated `secret.yaml` contains local credentials and must not be committed. Use `--no-save-password` when password persistence is not wanted.

### 0.2.0-68

The standalone Kubernetes wizard now emits the legacy-compatible HAProxy ingress annotation `kubernetes.io/ingress.class: haproxy` every time HAProxy ingress is selected, while retaining the Kubernetes v1 `ingressClassName` field. Reverse-engineering documentation also includes the latest Cluster transport evidence.

## 0.2.0-73
macOS ARM native-dialog reliability fix: project creation and Import & Separate now wait for the native pywebview bridge readiness event, tolerate delayed WebKit bridge injection, and keep modal interactions from closing the dialog unexpectedly.
