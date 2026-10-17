# Server AI installation and safe project/job lifecycle — 0.3.0-r210

This is a full cumulative source package based on the Windows-startup/Arranger-tabs
cumulative. VERSION=0.3.0 and REVISION=210 are unchanged. No commit, push, tag,
release, live installation or production billing activation was performed.

## Complete AI installation by default

The chosen entry point is `scripts/install_mta.sh`, including signed RPM/DEB mode.
Heavy network/model dependencies are provisioned by the installation wizard rather
than inside RPM/DEB transaction scripts. Plain APT/DNF package installation still
installs the web runtime and the signed provisioning helpers; completing server
setup with `install_mta.sh` installs the AI runtimes automatically.

- The signed RPM/DEB carries `install_ai_engines.py` and the same stems, lyrics,
  chords and RoFormer dependency manifests used for native builds.
- New installations retain local ACE-Step as the default. Its existing installer
  installs and starts it. Explicit existing local/remote/disabled ACE preferences
  are retained; disabling ACE does not disable the other installed AI engines.
- Demucs, Whisper, chord/marker dependencies, ONNX DrumSep, audio-separator and SAM
  Audio/singer separation are provisioned by default. Common audio and SAM runtimes
  are separate, and neither replaces the web runtime nor ACE's installed torch.
- CPU, CUDA and ROCm select their appropriate torch wheel triplets. ROCm also uses
  the CUDA API exposed by PyTorch. GPU setup verifies availability and a small
  actual tensor operation; it does not certify GPU accounting or enable billing.
- Runtime environments use versioned final paths (venvs cannot safely be moved).
  A ready environment is rechecked and reused. Imports and compiled torchvision
  operators must pass before the pending configuration receives any new binding.
  Failure leaves the live environment bindings unchanged. Existing SMTP settings,
  secrets and ACE endpoints are retained. Model-default settings preserve existing
  administrator choices.
- `app/ai_install_catalog.py` covers every built-in worker kind, including ACE
  aliases. The regression gate rejects adding a future built-in worker without
  installation coverage. Future engines must declare their recipe and requirements.
  Operator-defined external engines still require their operator-provided runtime.
- The server model manager delegates lyrics/chords downloads to the configured AI
  interpreter, avoids recursive delegation, and recognizes/deletes Whisper cache
  files even when Whisper is absent from the web interpreter.
- Checkpoints are cached/downloaded on demand, as in the native application. This
  does not download all model sizes or claim their licenses/access are satisfied.
  SAM checkpoints require Hugging Face authorization and upstream access approval:
  https://github.com/facebookresearch/sam-audio . The upstream code revision used
  for SAM installation is resolved to a full commit and retained in the runtime.
- Default DrumSep fetches through the existing native downloader and its fixed
  SHA-256 verification before inference. An explicit missing model override fails.
  Existing queue, token authorization and verified-accounting gates are preserved.

For an already-upgraded signed package, complete provisioning while the AI queue
is idle (the existing wizard restarts services at the end):

```bash
sudo bash scripts/install_mta.sh --configure-only --unattended
```

Use the interactive path without `--unattended` to review/change the saved hardware
and ACE preferences. Dry-run of the all-engine plan without modifying the host:

```bash
python scripts/install_ai_engines.py --dry-run --device auto
```

Internet access is required for AI dependencies and later checkpoint downloads.
On a machine whose new signed package lacks the helper, the wizard fails with an
upgrade instruction rather than fetching an unsigned replacement helper.

## Results are durable before notifications

- AI publication changes a server-owned publication token in the same atomic JSON
  write as the generated tracks/annotations. A stale whole-project PUT is rejected
  with HTTP 409 `PROJECT_AI_RESULTS_CHANGED` under the project publication lock.
- A stale autosave reloads the authoritative project and conservatively reconciles
  new AI tracks/assets with local edits before retrying. Explicit deletions of
  previously known tracks remain deletions. Conflicting annotation edits are not
  silently overwritten: saving/navigation stops and the local edits remain present.
- The independent job monitor awaits project reconciliation before showing or
  acknowledging a completion notice. It tracks the actual origin/progress DOM
  for Arranger, stems and text extraction. A separate completion notice appears
  only after that origin window has been closed. Automatic Arranger closure after
  successful completion does not cause a duplicate notice.
- Native bound files are synchronized before completion notice display, including
  projects closed in the editor while the job was running. Errors prevent the
  completion flow from claiming successful persistence. Unbound native projects
  remain durably stored in the workspace.

## Unsaved changes when leaving a project

Closing, switching, creating/importing another project and internal navigation
check for unsaved changes. The check compares the actual project to its saved
snapshot, so it also detects edits whose handler did not set a dirty flag.

With autosave enabled the editor waits for a successful strict save. With it
disabled, the dialog offers Save / Discard changes / Cancel. An active annotation
editor is committed before the project save. Failed saves keep the current
project open; native bound-file write failures are propagated too.

The native OS-window close event waits for the same guard before destroying the
window. Its JavaScript check is dispatched asynchronously after the synchronous
OS closing callback returns, keeping the WebView UI thread free. Browser reload/tab close uses the standard beforeunload confirmation;
browsers control that dialog and do not permit waiting indefinitely for async work.
Intentional internal navigation uses the explicit save/discard/cancel guard.

## Validation and remaining functional checks

Executed test counts, coverage, skips and runner exclusions are recorded in
`validation/r210-ai-install-lifecycle-report.json` and its JUnit/log companions.
Tests execute the production JavaScript with isolated HTTP/DOM harnesses and test
real persisted WAV publication/stale PUT rejection, native-close control, installer
transactionality, future-engine coverage and actual package payload fixtures.

The Linux test runner cannot execute Win32 APIs or a native installer. Ten existing
Unix-socket agent cases remain deselected because AF_UNIX creation is prohibited;
four optional SDK tests and the real Win32 API test are skipped.

The heavy AI installation itself, gated checkpoint authorization, fresh RPM/DEB
provisioning and real CPU/GPU inference have not been executed here. Validate on
the target server after CI/Matrix/Publish: run setup, check every engine once,
close each job's origin window and verify notification ordering, reopen the result
project, and exercise Save/Discard/Cancel plus native bound-file persistence.
GPU billing certification remains dependent on the existing hardware evidence
and calibration gates; these changes do not certify the production server.
