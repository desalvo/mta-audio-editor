# Testing, CI/CD and release process

## Local validation

Minimum pre-release checks:

```bash
python -m compileall -q app scripts/k8s-wizard.py
python -m pytest -q
```

CI additionally runs coverage and security/static-analysis checks.

## Test families

The suite covers:

- Pydantic model validation;
- non-destructive editing/ripple;
- plugin configuration;
- Auto Mix;
- authentication/session lifecycle;
- TOTP;
- SMTP;
- workspace isolation/sharing;
- complete project archive round-trip;
- administrator dump;
- Kubernetes wizard generation;
- production security behavior;
- mobile UI regression;
- MTA proprietary parser/transport invariants.

## Coverage

The CI workflow enforces a minimum application coverage threshold. New features should add tests rather than lower the gate.

## Security gates

Expected gates include:

```text
Ruff
Bandit
pip-audit
Gitleaks
Trivy filesystem
Trivy container image
CodeQL
```

## Container gate

The production container gate:

1. builds the image;
2. runs vulnerability scan;
3. starts the service with CI bootstrap credentials;
4. waits for `/api/health`;
5. verifies anonymous API rejection;
6. verifies browser protected-page redirect behavior;
7. verifies request-integrity behavior.

## Publish policy

A push to `main` builds/publishes `latest` when all required gates pass.

A version tag publishes the corresponding version tag.

Multi-architecture publication targets amd64 and arm64 where configured.

## Release artifact

The downloadable project ZIP is GitHub-ready and includes:

- source code;
- Kubernetes/Docker assets;
- documentation;
- generated PDF manuals;
- tests;
- release notes.

A `.sha256` sidecar is generated for integrity verification.

## Version/build identity

`VERSION` stores the public product release (for example `0.2.0`).

`REVISION` stores the source/package revision within that release (for example `153`). It is not a build number.

`BUILD_INFO` stores the generated 14-digit build timestamp and remains independent from the revision.

Stable Git tags use `v< VERSION >` (for example `v0.2.0`). Release assets may include `-r<REVISION>` to identify the exact packaged revision. Runtime `/api/about` exposes version, revision, combined release identity, and build separately.

## Final acceptance checklist

Before declaring a release final:

```text
[ ] compileall passes
[ ] pytest passes
[ ] coverage gate passes
[ ] docs PDFs rebuild successfully
[ ] PDFs visually inspected
[ ] Kubernetes wizard sample manifest generated
[ ] no secrets embedded in release
[ ] proprietary MTA XOR round-trip tests pass
[ ] canonicalized generated MTA is FFprobe-readable
[ ] GitHub Actions green
```

Physical M-Live/Merish acceptance remains a separate device/firmware qualification step.


## Documentation publication gate

Every release that changes UI behavior, MTA handling or mobile connectivity must rebuild the bilingual manuals:

```bash
python scripts/build_docs.py
```

The release gate must verify:

- IT/EN user and administrator PDFs are generated;
- page 1 is the photographic product cover with logo, version/revision/build and supported platforms;
- headings are kept with the beginning of the following paragraph/table/figure;
- the PDFs render without clipping or overlap;
- the MTA format documents are synchronized with current reader/writer behavior;
- the mobile default server is not printed in user-visible documentation or UI.


## Documentation build and PDF QA

The integrated manuals are authored as HTML and generated with:

```bash
python scripts/build_docs.py
```

Required release checks:

1. build both User and Administrator manuals in Italian and English;
2. render each PDF to PNG pages;
3. visually inspect every page for clipping, overlap, missing images/glyphs and cover quality;
4. confirm the first page is the photographic project cover with logo, version/revision/build/creator/license/repository and supported platforms;
5. verify headings are kept with at least the beginning of their following content block;
6. verify the built-in mobile default service URL does not appear in user-facing manuals/mobile documentation;
7. run the full test suite after PDF regeneration.
