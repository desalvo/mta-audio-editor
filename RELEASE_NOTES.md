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
