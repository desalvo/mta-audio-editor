# ACE-Step 1.5 source bundling in GitHub Actions (r195)

Use **Actions → ACE-Step audited source bundle → Run workflow**, supplying a **reviewed full 40-character upstream Git commit SHA** from `ace-step/ACE-Step-1.5`. No floating `main` or `latest` is accepted. The CI fetches upstream source, checks checkout identity, preserves MIT licensing, rejects checkpoint weights and uploads a deterministic source tarball with SHA256 checksum. `dependency_probe` can also attempt an isolated Python 3.12 dependency installation on Ubuntu, but actual GPU runtime compatibility must be reviewed per target platform.

**Current boundary:** This workflow produces an independently downloadable **audited source artifact**. It does not yet embed a self-contained, fully resolved Python/GPU runtime in native Windows/macOS/Linux installers or build and publish an MTA ACE-Step container image. The source artifact must be integrated into the existing native and container build stages after downstream dependency and checkpoint license audits. It does not install code onto user machines; it transfers that work into the trusted release build. Checkpoints remain on-demand on persistent storage. Do not assert AI Arranger or Remix operational until a real backend performs generation and MTA plays/imports its output.

Release permissions: do not vendor model weights; review dependencies and preserve license notices. If upstream changes license or layout, validation fails and a maintainer must audit the new revision. Remote MTA clients should use authenticated MTA APIs; do not publicly expose the ACE-Step service.

## Default upstream version and automatic update proposals (r195)

- The default **stable ACE-Step version is `v0.1.8`** (latest release verified on 2026-10-11), recorded in `ace_step_version.json`.
- The manually triggered `.github/workflows/ace-step-bundle.yml` action can run without a SHA input: it resolves the locked release tag through upstream Git refs to its **full immutable commit SHA** and bundles exactly that source revision. An explicitly reviewed 40-character SHA remains available as an override.
- `.github/workflows/ace-step-update.yml` checks GitHub's `releases/latest` each Monday, or when manually dispatched. If the stable version changes, it **opens a pull request** updating the default tag. The new version is not adopted by release builds until the pull request is reviewed and merged.
- The repository must permit GitHub Actions to create pull requests. If organization/repository policy disables this, the workflow will fail and the existing locked release remains in effect.
- Review new dependencies, source/model licensing, runtime compatibility and live audio regression before merging any update. CI still emits a **source artifact only**: it does not yet bundle a production-ready Python inference environment in native installers or GPU container images. Checkpoints remain on-demand in persistent volumes.
