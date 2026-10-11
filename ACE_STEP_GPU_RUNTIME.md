# ACE-Step pinned GPU server image (r196)

The `ACE-Step pinned GPU runtime image` workflow creates a CUDA `linux/amd64` container **from the exact reviewed upstream Git commit** referenced by `ace_step_version.json`. It builds with the official upstream Dockerfile and publishes to GitHub Container Registry; no weights are shipped. This replaces the previous unaudited `latest` image in Compose.

## First run

1. In Actions, run `ACE-Step pinned GPU runtime image` on main. `packages: write` is declared in the workflow; repository or organizational rules must permit package publishing.
2. From the successful workflow's step summary, copy the resulting image tag. Set `MTA_ACE_STEP_IMAGE=ghcr.io/<owner>/mta-ace-step:<12-character-commit-prefix>` in your `.env`. Do not assume the build succeeded until the Actions run is green.
3. On a Linux host with compatible NVIDIA drivers and NVIDIA Container Toolkit, configure Docker GPU access, then `docker compose up -d`. The ACE-Step container requires GPU allocation; edit Compose or use `docker-compose.gpu.yml` below. See the GPU service override.
4. On first inference, ACE-Step may download model weights to the named `ace-checkpoints` and `ace-hf-cache` volumes; these survive container restarts and are readable by MTA for cache diagnostics. Remote clients use MTA's authenticated APIs, **not** the ACE-Step port.
5. Run the live AI smoke test against the deployed MTA/ACE-Step combination, then generate and audition a real audio clip in MTA. GPU inference has NOT been verified by this source release.

> This workflow generates a Linux CUDA image only. It does **not** yet package the ACE-Step Python environment in Windows/macOS/Linux native installers. The native desktop manager still requires local `git`/`uv` for first installation. These remain blockers for the requested turnkey experience.

The checkpoint license and dependency notices must be reviewed independently before redistribution. Weights remain on-demand.
