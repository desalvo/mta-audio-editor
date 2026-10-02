## 0.2.0-63

- Corretto il secondo errore Android rilevato nel run GitHub Actions 37057175276: il progetto usa dipendenze AndroidX ma non abilitava `android.useAndroidX`.
- Aggiunto `mobile/android/gradle.properties` con AndroidX abilitato e Jetifier disabilitato, dato che le dipendenze del progetto sono già AndroidX.
- Aggiunto test regressivo per impedire la rimozione accidentale della configurazione AndroidX.


## 0.2.0-63

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

# MTA Audio Editor 0.2.0-63

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

### 0.2.0-63

The standalone Kubernetes wizard now emits the legacy-compatible HAProxy ingress annotation `kubernetes.io/ingress.class: haproxy` every time HAProxy ingress is selected, while retaining the Kubernetes v1 `ingressClassName` field. Reverse-engineering documentation also includes the latest Cluster transport evidence.
