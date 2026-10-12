# Native server packaging — r208 staging

Native **server** package name is `mta-audio-editor-server`, never the desktop `mta-audio-editor` and never `mta-proxmox-gpu-agent`.

This increment delivers offline DEB/RPM package **builders**, service definitions and validation gates. It does **not** yet certify multi-distribution installation, migration, package signing or automatic repository publication. `install_mta.sh` intentionally continues to use its established install mode until CI and migration have passed.

## CI staging contract

Generate a complete `stage/` with `application/` (server source without `.git`) and `wheelhouse/` (all pinned/transitive wheels for **each supported Python ABI / architecture**, obtained from trusted indexes, hashed and audited in CI). Verify licenses, platform compatibility and `pip install --no-index` in a clean test VM. Never mix architectures in a published artifact. Set an explicit supported Python runtime: Debian 13 and Ubuntu 24.04 can use Python >=3.12; Debian 12 / EL9 require a validated alternate Python >=3.12 and compatible wheels. Do not silently replace the OS system Python.

Example build on a suitable isolated packaging runner:

```bash
python3 scripts/server_packages/wheelhouse_lock.py create stage
python3 scripts/server_packages/wheelhouse_lock.py verify stage
python3 scripts/server_packages/validate_stage.py stage
MTA_SERVER_STAGE="$PWD/stage" MTA_SERVER_VERSION='0.3.0~early.208' MTA_SERVER_OUTPUT="$PWD/dist" bash scripts/server_packages/build_deb.sh
MTA_SERVER_STAGE="$PWD/stage" MTA_RPM_VERSION='0.3.0' MTA_RPM_RELEASE='0.208.early' MTA_SERVER_OUTPUT="$PWD/dist" bash scripts/server_packages/build_rpm.sh
```

The packaging scripts require **prebuilt** wheels, never contact PyPI, and do not create or push a GitHub release. Installations preserve `/etc/mta/mta.env`, `/var/lib/mta`, and models. No automatic takeover of a legacy git-managed `/opt/mta/application` occurs: migration needs a separate, reversible procedure and downtime window.

## Not ready for production

Before publishing: implement wheel lock and hashes; test target ABIs; verify systemd unit arguments and persisted directories; VM-based install/upgrade/rollback for Debian/Ubuntu/Rocky, signing and public-key distribution; fix service hardening against the actual app write paths; migrate existing wizard installs with a backed-up rollback; complete `install_mta.sh` switch with explicit early/stable pinning. Repository publishing stays disabled until all gates pass.

## Wheelhouse integrity gate (r208)

Both native builders now require `wheelhouse.lock.json` alongside `application/` and `wheelhouse/`. Generate the manifest **after** constructing wheels in CI, then verify it immediately before packaging. The manifest records SHA-256, byte length and filename for every wheel; corrupt archives and modified payloads are rejected. This protects staging integrity but is **not** a dependency resolver or supply-chain provenance signature. Production CI must additionally pin transitive dependencies, validate Linux ABI/architecture, scan licenses/vulnerabilities and test a real offline installation on each supported OS. Publishing remains disabled.

## Offline runtime closure gate (pre-commit r208 update)

On each **actual target OS, architecture and Python runtime**, CI first assembles a
complete wheelhouse and creates `wheelhouse.lock.json`. Run:

```bash
python3 scripts/server_packages/verify_offline_runtime.py stage --write-proof
MTA_SERVER_RELEASE_READY=1 MTA_SERVER_STAGE="$PWD/stage" MTA_SERVER_VERSION='0.3.0~early.208' MTA_SERVER_OUTPUT="$PWD/dist" bash scripts/server_packages/build_deb.sh
```

The resolver runs `pip install --dry-run --ignore-installed --no-index --only-binary=:all:`
against **only** staged wheels. It fails if any transitive requirement is missing
or incompatible with the running interpreter. `offline-runtime-proof.json` binds
the SHA256 of the requirements and wheelhouse manifest to OS, architecture and
Python version. With `MTA_SERVER_RELEASE_READY=1`, both builders require this
proof. A fixture smoke build without that flag is **not release ready**.

This proof is not a cryptographic CI attestation and does not replace verified
wheel origin, vulnerability/license auditing, actual installation in a clean VM,
or upgrade/rollback testing. Publish remains intentionally disabled. Keep the
proof generation and packaging on the same target runner; validate each distro
separately, because equal kernel/CPU identifiers do not guarantee equal ABI.

### CI runtime closure validation (r208)

`scripts/server_packages/prepare_runtime.py --source . --stage /tmp/server-stage --requirements requirements.txt`
creates a **new** staging directory, downloads a binary-only, transitive wheelhouse on the
**target interpreter and architecture**, hashes the entire wheelhouse, verifies pip
resolution with `--no-index`, and writes a proof bound to the Python version and CPU.
It intentionally fails when dependencies cannot be resolved; it never silently builds
sdists. Never reuse proofs from other runners. The `server-native-runtime-validation.yml`
workflow is currently *validation only*: it does not sign or publish packages, and
its Debian 12/Python 3.12 job is not an OS-packaging certification. Full install,
upgrade, native-library and rollback tests remain required before enabling repos.

## Native opt-in / legacy migration guard (r208)

`install_mta.sh --native-server stable|early [--dry-run]` delegates to the native installer, which requires a published HTTPS repository URL and the operator-supplied, independently verified **full** 40-hex GPG fingerprint. It refuses to take over an existing wizard-managed checkout. The legacy path remains the default until VM transaction tests and a reversible migration workflow have been approved.

The Debian `preinst` and RPM `%pre` reject a detected legacy checkout **before installing payload files**; this prevents accidental replacement during `apt install` / `dnf install`. These guards do not implement migration or backup by themselves. Do not enable unattended repository release from CI yet.
