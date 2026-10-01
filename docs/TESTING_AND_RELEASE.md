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

`VERSION` stores the project release.

`BUILD` stores a generated build timestamp.

Runtime `/api/about` exposes release/build identity.

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
