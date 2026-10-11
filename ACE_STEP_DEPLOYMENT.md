# Integrated ACE-Step service — 0.3.0-r189

## Status
This release includes an **ACE-Step service** in the Docker Compose and Kubernetes manifests and a **desktop local-process launcher**. Model files are **not included in images or installers**; upstream ACE-Step downloads missing checkpoints on demand or at first model initialization. Actual model inference is **not certified**: run a real cover task against a compatible GPU node before exposing the feature.

## Docker Compose
`docker compose up -d` starts the MTA service and the ACE-Step API in a second container. The model API is **not published to host ports**. The editor reaches it by trusted Docker DNS hostname `ace-step` on port 8001. `MTA_AI_WORKER_ENABLED=true` and the bundled executable adapter are preconfigured. Volumes `ace-checkpoints`, `ace-hf-cache` and `ace-output` keep model weights and results across restarts. The image itself contains no models. ACE-Step must be allowed outbound HTTPS for first-use downloads; offline nodes require pre-seeded model volumes.

**GPU**: configure an NVIDIA Container Toolkit capable host and add a compose GPU reservation to `ace-step` appropriate to the host. CPU inference may not be practically usable. Pin and independently review the upstream container digest before production deployment. Upstream ACE-Step image: `ghcr.io/ace-step/ace-step-1.5`.

## Kubernetes
`k8s/base/deployment.yaml` includes the API as a *same-pod sidecar*, reachable only by MTA on loopback (`127.0.0.1:8001`); no Service or Ingress exposes the ACE endpoint. Checkpoints and Hugging Face cache have PVCs (30 GiB each). Configure GPU requests/limits and suitable CUDA nodes as needed. Since model weights are fetched at the initial initialization, `ACESTEP_INIT_SERVICE=false` permits starting the API without eagerly downloading models; **model acquisition at first actual inference depends on the upstream server behavior and must be validated**. The container may require custom security, permissions, writable cache mounts, GPU runtime, and init-service settings on the selected host. Run `kubectl apply -k k8s/base/` only after adapting these requirements.

## Native desktop (Windows / macOS / Linux)
`python -m app.ace_step_local --executable /ABSOLUTE/PATH/TO/acestep-api --allow-model-download` launches an **already installed** upstream ACE-Step CLI in a subprocess with persistent model cache (`~/.cache/mta-audio-editor/ace-step`). This is a first integration step, not yet a one-click installer. Users must install an approved compatible upstream version/environment first. The model download remains in the upstream tool; no arbitrary internet scripts are executed by MTA.

## Security and licensing
ACE-Step is a separate upstream dependency. Do not expose its REST port publicly. Only loopback addresses or the exact trusted sidecar hostname provided by `MTA_ACE_STEP_TRUSTED_HOST` are accepted; HTTP redirects are rejected. Before redistribution verify the licenses of code, models and transitive dependencies for the selected upstream digest and ensure notices are included. Avoid pulling unpinned third-party images in production.

## Operational readiness
Arranger and Remix cover generation must pass a real audio-in/audio-out test, preview and non-destructive import from both track and Master Out. Selective Instrument Swap still needs a separate verified pipeline. `native_host_ready` remains false for the compiled VST3/realtime host.

### r190 readiness diagnostics
`app.ace_step_readiness.readiness(probe=True)` checks worker declarations. Set `MTA_AI_READINESS_PROBE_SERVER=true` for a separate reachability check. Neither probe certifies that the model has generated audio. A real end-to-end track/master generation, preview playback and successful non-destructive import remain the acceptance criteria.
