# MTA Audio Editor 0.2.0-8

This release fixes the remaining GitHub Actions failure observed after 0.2.0-7.

## CI/security fix

The smoke-test Basic Auth password is now generated dynamically at workflow runtime. This removes the Gitleaks `curl-auth-user` false positive while keeping the secret scan enabled and strict.

## Retained functionality

All 0.2.0-7 functionality is retained, including verified read-only decoding of MTA `LYRICS`, `CHORDS`, `COLORS`, and `MIDITK`, standard MIDI reconstruction, EBML attachment fallback, project architecture documentation, and MTA format research notes.

## Validation

The package continues to target Python 3.11 and the same production quality/security gates.
