# ACE-Step shared model cache and remote MTA clients (r194)

The ACE-Step service remains internal to the Compose network or Kubernetes pod. Remote desktop/mobile clients access **MTA authenticated project endpoints**, never expose ACE-Step port 8001 to the Internet. TLS, authentication, user/project authorization, request limits and GPU-job admission control are deployment requirements before opening remote access.

- Docker Compose: `ace-checkpoints` and `ace-hf-cache` named volumes persist across recreations; the MTA container mounts them **read-only** for cache metrics.
- Kubernetes: `mta-ace-checkpoints` and `mta-ace-cache` PVCs persist independently of pods, and MTA mounts them read-only. The default RWO access mode is suitable for same-pod use; multiple replicas/nodes require compatible RWX storage or external model-serving architecture. Do not scale duplicate ACE-Step pods sharing RWO volumes across nodes.
- `GET /api/ai-arranger/model-cache`: authenticated aggregate bytes/file counts only. An occupied cache **does not prove** model readiness. No model files, hashes, absolute paths, or filesystem listing are disclosed.
- ACE-Step downloads missing model weights when the upstream runtime initializes them; whether on-demand download succeeds depends on checkpoint manifests, permissions, network and GPU. Validate live inference before using the feature.
- Model licensing: inspect exact checkpoint and dependency license before redistributing; no weights are included.
- Reproducible offline **code** bundling: `scripts/vendor_ace_step.sh <audited-full-commit-sha>` creates a reviewed source snapshot from upstream, preserving its license; run during a network-enabled release build. In this r194 package the upstream source is **not** vendored, because retrieval could not be completed here. Do not mistake the script for an already embedded backend.
