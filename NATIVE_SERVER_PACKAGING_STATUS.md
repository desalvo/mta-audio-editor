
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
