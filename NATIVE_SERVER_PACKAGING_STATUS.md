
## r208: offline extracted-payload CI validation

The validation workflow now builds release-gated DEB on Debian 13 (Python 3.13)
and RPM on Rocky Linux 9 (Python 3.12), extracts the generated native archives,
creates temporary virtual environments, installs exclusively from the **extracted**
wheelhouse (`--no-index`), runs `pip check`, and imports the application entrypoints.
The package files are uploaded as **unreleased test artifacts only**.

These tests do **not** cover transaction scripts, OS-level dependency resolution,
service activation, upgrades/rollback, or migrations of existing Git deployments.
Neither GitHub Pages publication nor `install_mta.sh` repository mode is activated.
The Rocky CI job needs live GitHub Actions verification before it can be declared passing.

## r208 — transactional offline runtime update (pre-commit)

- DEB postinst and RPM post use one `install_runtime.py` implementation.
- Constructs a new venv in a staging sibling directory, installs strictly with `pip --no-index`, runs `pip check` and imports required server entrypoints before promotion.
- Keeps the previous managed venv until the new environment passes checks. On deployment error during promotion, restores the previous managed venv.
- Fails closed if an older rollback directory exists; operator review required.
- Does not migrate a Git/wizard-managed installation automatically, and does not modify projects, models or secrets.
- This is **not yet a release-ready transactional OS-package upgrade**: package payload and service restart rollback, storage migration, system-level APT/DNF install tests, and a full CI run are still pending. Repository publishing stays disabled.

## r208 pre-commit consolidation: CI installation gate

- Debian 13 CI now attempts real `apt-get install` and reinstall of the generated offline server DEB in a disposable container.
- The integration test checks installed-package state, runtime `pip check`, and preservation of `/etc/mta/mta.env` and a test project file.
- The test refuses to run without the explicit disposable-container CI guard.
- It is **not yet validated in GitHub Actions**. RPM DNF transaction, rollback, legacy migration, signing keys, repository deployment and external release validation remain outstanding.
- Public repository publishing remains disabled and must not be described as production-ready.

## CI improvements after successful Quality and repository tooling runs (2026-10-12)

* Native server runtime matrix now runs on pushes to `main` when packaging, application, requirement or relevant test paths change, in addition to pull requests/manual triggers.
* Repository tooling validation also tracks `scripts/server_packages/**` and packaging regression tests; changing unrelated Proxmox tests does not trigger it.
* RPM integration test `scripts/server_packages/test_rpm_upgrade.sh` verifies `dnf install`, `dnf reinstall`, preserved `/etc/mta/mta.env` and project fixture, and `pip check`. It **must** be run only with `MTA_CI_DISPOSABLE_CONTAINER=1` in a disposable isolated image with trusted FFmpeg repository configured; current Rocky 9 CI runs a guard test, not the full DNF install.
* RPM `%post` creates the administrator credential file under a restrictive umask and rejects wizard marker files.
* APT install/reinstall CI is already present. Neither package publication nor automatic migration of the production CT is enabled.

## Production gate review (2026-10-12, r208; no commit/push)

**NOT CERTIFIED FOR PRODUCTION.** The following are mandatory external sign-offs:

1. GitHub Actions must pass on the exact release commit for Debian 13 native runtime/DEB install and Rocky 9 runtime/RPM build. No successful new run is asserted here.
2. A disposable Rocky 9 runtime must execute *actual* DNF install/reinstall with trusted FFmpeg packages and check systemd service lifecycle and saved state. The existing Rocky CI verifies only RPM payload and the destructive-test guard.
3. Ubuntu 24.04 Python 3.12 must build its own ABI-matched wheelhouse/DEB and perform APT lifecycle tests. Debian 12's default Python 3.11 does not meet requirements and is not supported by a generic DEB.
4. Confirm service start, HTTP health, admin bootstrap, secrets permissions, scheduler, data persistence, upgrade and downgrade/rollback on separate clean test hosts.
5. Create and secure the release GPG identity; sign RPMs and both repository metadata sets using an isolated, protected publisher; verify signature and provenance from a separate client before any publication.
6. Approve migration of the existing wizard/Git deployment separately with verified backups and recovery rehearsal. Current native installation refuses to overwrite such deployments. Do not migrate CT 130 yet.
7. Review third-party licenses, required codecs, package availability on Rocky 9, SBOM, vulnerability scanning and supported-OS contracts. No unreviewed third-party repository should be configured automatically in production.

Improvements in this iteration: RPM release validation now runs under Python 3.12 rather than the potentially different default `python3`; DEB release packages carry a bounded Python 3.12/3.13 dependency range; the promoted venv is revalidated after being moved before deleting rollback; Debian postinst detects both legacy Git and wizard markers.

## Completion gate additions (r208, pending next CI)
- Native server matrix includes Ubuntu 24.04/Python 3.12 build and DEB install/reinstall, alongside Debian 13.
- Rocky Linux 9 matrix attempts actual DNF install/reinstall with EPEL `ffmpeg-free` providing `/usr/bin/ffmpeg`; this **must pass in remote CI** before claiming RPM availability. RPM dependency is on the FFmpeg executable.
- Server installation scripts also import application entrypoints after install and reinstall.
- Repository tooling has an additional disposable CI job generating an ephemeral GPG key, signing an APT fixture, and verifying it with apt. It does **not** sign/publish actual production releases.
- Real systemd startup/health under PID 1, interrupted package-manager transaction rollback, RPM repository signature end-to-end, native legacy migration and production private-key provisioning remain unverified; do not label a release production-certified until these are tested and evidenced.
