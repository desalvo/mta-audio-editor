# Contributing

Contributions are welcome through pull requests against `main`.

1. Create a focused branch and do not commit secrets, generated project data or credentials.
2. Install development requirements with `python -m pip install -r requirements-dev.txt`.
3. Run `./scripts/production_gate.sh` before opening a pull request.
4. Add or update tests for behavior changes. The repository enforces a minimum aggregate coverage of 70%.
5. Treat files uploaded by users, MTA metadata and project JSON as untrusted input.
6. Never build subprocess command lines through a shell; pass explicit argv lists and validate filesystem paths.
7. Report security issues according to `SECURITY.md`, not in a public issue.

By contributing you agree that your contribution is provided under EUPL-1.2 and that you have the right to submit it.
