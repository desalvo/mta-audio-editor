# Security policy

## Supported versions

Security fixes are applied to the latest released version of MTA Audio Editor.

## Reporting a vulnerability

Do not publish exploitable details in a public issue. Report the problem privately to the project owner, Alessandro De Salvo <braket71@gmail.com>, including affected version, reproduction steps, impact, and any proposed mitigation. Avoid attaching real confidential audio projects unless strictly necessary.

## Security design

The application follows a secure-by-default deployment model: authentication is enabled by default, no default administrator password is embedded in the image, uploads are size limited, project identifiers are validated before filesystem access, external media processing uses argument-vector subprocess invocation rather than shell execution, containers run as an unprivileged user, Kubernetes manifests use a restricted security context, and production CI gates include linting, tests, dependency audit, SAST, filesystem/image vulnerability scanning, and container build validation.

The security baseline and deployment responsibilities are documented in `docs/SECURE_DEVELOPMENT.md`. The mapping is guidance-oriented and is not a formal certification.
