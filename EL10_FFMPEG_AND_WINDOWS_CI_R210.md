# EL10 FFmpeg and Windows CI fixes — 0.3.0-r210

Full cumulative package based on `MTA-r210-server-ai-install-project-lifecycle-cumulative.zip`
(SHA-256 `58f0c3c40fd48186980f595e0bfbcae69c82346446b0e6b9874f107d316e1abe`).
Version and revision are unchanged. No Git mutations or live-server changes.

## EL10 setup failure

The all-engine installer requested an RPM named `ffmpeg`. The reported EL10 host
already has `ffmpeg-free` installed, while its configured package metadata does
not contain a package named `ffmpeg`. This made the whole dependency transaction
fail before AI environment provisioning.

`scripts/install_ai_engines.py` now installs build dependencies separately from
media tools. It checks FFmpeg and FFprobe on PATH, reuses working executables,
and verifies each with `-version`. When a tool is absent, the RPM path requests
its file capability (`/usr/bin/ffmpeg` or `/usr/bin/ffprobe`); DNF chooses the
provider from already configured repositories. APT continues using its `ffmpeg`
package when media executables are missing. A broken binary or a missing binary
after a nominally successful package transaction remains a setup error.

The legacy-source RPM bootstrap uses the same file capabilities. No repositories
are enabled or added by this correction, no FFmpeg variant is forcibly replaced,
and AI accounting/safety checks are unchanged.

## Windows CI failure from the attached log

The log shows 10 passing tests and one failure in the CSS contrast test:
`UnicodeDecodeError` while the Windows CP1252 default decoder reads UTF-8 CSS.
The test now explicitly reads `app/static/app.css` with `encoding='utf-8'`.
The log also confirms that the startup/publication/OS-lock tests passed on the
Windows runner before this encoding failure. It does not demonstrate a successful
installer build after the failed test step.

## Verification

The new regression cases cover:

- existing EL10 ffmpeg-free-style executables without requesting an RPM named ffmpeg;
- only FFmpeg missing, only FFprobe missing, and both missing;
- Debian package selection;
- broken binaries and providers that do not expose the required executable;
- the legacy RPM capability request and explicit UTF-8 CSS reading.

Executed pytest counts, coverage and static checks are included under
`validation/r210-el10-utf8-*`. The full regression retains the existing ten
Unix-socket exclusions because this runner prohibits AF_UNIX creation. Four
optional native SDK tests and the real Win32 API test are skipped locally.

Real EL10 provisioning, Windows CI/build and hardware AI inference were not run
here; these must be rerun on their respective targets. The production server is
not declared certified by these fixes.

After committing/building/publishing and installing the updated signed package,
resume the existing server setup with an idle AI queue:

```bash
sudo bash scripts/install_mta.sh --configure-only --unattended
```

The existing saved wizard answers/checkpoint remain available. `ffmpeg-free`
does not need to be replaced if FFmpeg and FFprobe work.

Suggested commit (since the checked-out user commit shown in the supplied CI log):

`Fix EL10 FFmpeg capability resolution and Windows UTF-8 regression test`
