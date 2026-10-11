# ACE-Step native desktop setup — r193

From the **AI Arranger / Remix** dialog in native single-user mode:

1. Click **Install ACE-Step**, review the consent dialog, and confirm. Git and `uv` must already be present and trusted on the computer. The manager clones the official ACE-Step 1.5 repository into the user data directory and executes `uv sync --frozen` in that checkout. This installs third-party software; it does not run a downloaded shell installer. Install is asynchronous; select **Refresh** for its status.
2. Click **Start local server**, granting permission to fetch model weights when the backend first initializes. Downloads are cached under `~/.local/share/mta-audio-editor/ace-step/models` by default (platform override via `MTA_ACE_STEP_DESKTOP_DIR`).
3. Click **Test real generation**. It runs a five-second opt-in actual audio inference, separate from ordinary health checks. Select **Refresh** to see `passed` / `failed` and the returned reason.
4. Generate and append a track only after the live test passes, and evaluate musical quality separately.

**Important**: Windows/macOS/Linux runtime support depends on the upstream ACE-Step and `uv` dependency set, GPU driver and available memory; no platform has been validated here with a real model. This is an opt-in managed installation workflow, **not a bundled, fully standalone installer**. `git` and `uv` are prerequisites. Native-only endpoints return HTTP 403 in multi-user/web/Docker deployments. Inference is not verified simply because the process launched. No model weights are bundled. Installer never updates an existing checkout automatically.

Installer source repository: https://github.com/ACE-Step/ACE-Step-1.5 ; pinning and signed upstream provenance verification should be completed before shipping this installer as a production feature. The local worker API must listen on `127.0.0.1:8001` and must not be exposed publicly.

### Progress indicators (r193)
The AI Arranger / Remix native setup panel polls desktop-ACE status while setup is in progress.
During Git clone, it displays Git's reported percentage when available. During `uv sync`, a moving indeterminate progress bar indicates activity because the dependency resolver does not provide a trustworthy total. On the first model initialization the bar is likewise indeterminate; the interface displays measured MiB added to the model cache during this MTA-owned session. It never reports a fabricated model download percentage. Installation and first model use require explicit consent. A previously approved local server starts with MTA and is stopped when MTA exits; processes not started by MTA are not affected.
