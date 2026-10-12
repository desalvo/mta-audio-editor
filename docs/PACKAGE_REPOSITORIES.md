# Native server packages: APT and DNF distribution

## Recommended hosting

Create a dedicated public GitHub repository `desalvo/mta-audio-editor-packages` and enable GitHub Pages (GitHub Actions source). Initially publish signed static indexes and small server packages at `https://desalvo.github.io/mta-audio-editor-packages/`. Do not publish until package install/upgrade tests and signatures pass. GitHub Pages has a published-site limit of 1 GB; use object storage/CDN when packages outgrow that limit.

The source repository `desalvo/mta-audio-editor` remains the build source; the package repository is published from vetted CI artifacts by a **separate restricted publisher**. Do not store signing private keys in the repository or expose them to pull request jobs. Use protected environments and a dedicated signing key, or an external signer; never grant untrusted jobs write permission.

## Channel and compatibility boundaries

- `early` follows qualified default-branch revisions, e.g. Debian `0.3.0~early.208-1` and RPM `0.3.0-0.208.early`.
- `stable` contains releases explicitly tagged `vX.Y.Z`, e.g. Debian `0.3.0-1` and RPM `0.3.0-1`.
- `mta-audio-editor-server` is **not** the native desktop package `mta-audio-editor`. Both need distinct package IDs, tests, and runtime dependencies.
- `mta-proxmox-gpu-agent` is separately installed on Proxmox hosts, not as a mandatory dependency of the LXC server.
- Keep application state in `/var/lib/mta` and host configuration in `/etc/mta` (not overwritten by upgrades); data migrations require backward-compatible or backed-up upgrade logic.
- Current checkout/venv installations **must not be overwritten** by a native package. Stop migration on ownership conflicts and provide an explicit, backed-up conversion path.

## Staging tools

`MTA_REPO_INPUT=/tmp/packages MTA_REPO_OUTPUT=/tmp/site MTA_REPO_CHANNEL=early MTA_GPG_KEY_ID=<full-40-hex-fingerprint> scripts/repositories/build_indexes.sh`

This creates a staging *flat* APT repository (`apt/early`) and optional RPM repository (`rpm/early`), and rejects unrelated/desktop packages. It requires Debian tooling (`dpkg-scanpackages`, `apt-ftparchive`), `createrepo_c`, `rpm`, and `gpg`. For RPM publication each RPM must already be signed. Do not use these artifacts for production until `apt install`, `apt upgrade`, `dnf install`, and `dnf upgrade` have passed in matching supported OS images.

To bootstrap a signed published repository after publication and release testing:

`MTA_PACKAGES_URL=https://desalvo.github.io/mta-audio-editor-packages MTA_REPO_KEY_FINGERPRINT=<full-40-hex-fingerprint> sudo -E scripts/repositories/install_repository.sh early`

The fingerprint must be obtained through an authenticated trusted channel **independent of the downloaded key**. Never disable `gpgcheck`, `repo_gpgcheck`, or APT signature validation. Avoid installing package updates from untrusted PR artifacts.

## Implementation gates still open

1. Build isolated and reproducible **server** runtime (including Python compatibility per target OS); the existing native DEB/RPM builder is for desktop only.
2. Package systemd service, app runtime, config preservation and install/upgrade scripts in native packages.
3. Exercise install, upgrade, downgrade safety and existing `/opt/mta` wizard migration on Debian/Ubuntu and Rocky Linux test systems.
4. Protect and configure the signing/publishing environment and Pages repo. Only then enable automatic channel publication.
5. Change `install_mta.sh` default from legacy checkout to package manager **only after** the server packages and migration gates pass; currently use bootstrap script explicitly.
