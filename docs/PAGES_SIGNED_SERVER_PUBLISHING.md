# MTA Audio Editor — definitive signed GitHub Pages server repositories

Canonical Pages root: `https://desalvo.github.io/mta-audio-editor-packages/`.

- APT early: `/apt/early/`; stable: `/apt/stable/`.
- RPM early: `/rpm/early/`; stable: `/rpm/stable/`.
- Signing key: `/mta-archive-key.asc`.
- Expected fingerprint: `0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7`.

## Required manual setup

1. Create the **public** repository `desalvo/mta-audio-editor-packages`, initialize `main`, and under Settings → Pages select **Deploy from a branch**, `main` and `/ (root)`. The Pages URL will not work until GitHub Pages has deployed.
2. Create an SSH **deploy key with write access** in that destination repository. Store its **private** half as environment secret `MTA_PAGES_DEPLOY_KEY` in the source repository, and retain the public half only in the destination repository's Deploy keys. Do not paste the private key into chat or commit it.
3. In the source repository create protected environments `server-early` and `server-stable`. Restrict the publisher to `main`, use mandatory reviewers for stable, and ensure the publisher has no approval bypass.
4. Put these environment secrets in both protected environments: `MTA_GPG_PRIVATE_KEY` (ASCII-armored export of the signing key), `MTA_GPG_PASSPHRASE` (the passphrase), and `MTA_PAGES_DEPLOY_KEY` (SSH key). The workflow is manual only (`workflow_dispatch`). The fingerprint is pinned as a **public constant**, not a secret.
5. Run **Native server offline runtime matrix** and require its **entire run** to be `success`, including Ubuntu VM/systemd acceptance and Debian/Rocky jobs. Copy its numeric run ID.
6. In source repository Actions → **Publish signed server packages to GitHub Pages** → Run workflow, enter the verified run ID and select channel `early` or `stable`. `stable` rejects prerelease version identifiers.
7. Verify the URL, check GPG signatures, then test fresh APT and DNF clients with `gpgcheck=1` and `repo_gpgcheck=1`. Keep public URLs HTTPS and pin the fingerprint on bootstrap.

This pipeline always checks that the CI run was a successful `push` on `main` **at the same source commit**. It only downloads named native-package artifacts from that run; other workflows and cancelled/failed runs cannot publish. Signing material is confined to the protected job. Publishing keeps the other channel intact.

## Security and limitations

- This is source-level implementation, **not** a confirmation of successful end-to-end signing or Pages deployment. RPM `rpmsign` loopback behavior must be verified by CI with the actual protected key.
- GitHub-hosted runners can access imported private signing material while publishing. Environment protection reduces exposure but is not equivalent to hardware-backed, offline signing. Use strict repo access, branch protection and secret rotation procedures.
- Repository contents are overwritten for the selected channel. Keep separate signed snapshots or immutable releases elsewhere for rollback and incident response.
- The server packages currently produced by the matrix are early-release builds. To enable `stable`, create actual stable-version packages and rerun the native qualification workflow.
- There is no upload on pull_request or unverified branch. Publishing must remain manual with approval for stable.
- GitHub Pages has storage and bandwidth limits. Verify release size/capacity before adopting it as a production package CDN.

**BLOCKING CAPACITY GATE:** regular GitHub repositories reject individual Git objects over 100 MiB. Native CI artifacts have already been observed around 130 MiB compressed, but the uncompressed DEB/RPM bytes must be measured. The publisher intentionally refuses oversized packages. No claim of production-ready Pages hosting is made until a compliant large-binary transport (e.g., object storage or a separate supported Pages deployment approach) is integrated and verified. Git LFS pointers in Pages are not a valid substitute for downloadable native packages.
