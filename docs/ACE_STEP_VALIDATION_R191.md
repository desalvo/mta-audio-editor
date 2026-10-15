# ACE-Step integration validation — r191

The project includes a real HTTP adapter which exchanges source WAV audio with the configured ACE-Step API, polls a task and validates the result. The `tests/test_r191_ace_http_e2e.py` exercises this actual HTTP transport with a **synthetic test server**, not with the ACE-Step model. This test validates request format, polling, download, and WAV decoding; it does **not** certify actual music generation, quality, identity preservation or selective instrument swaps.

In r191 the adapter also explicitly disables environment-configured HTTP proxies for local/internal-server traffic and rejects non-JSON health responses. The worker should be deployed on a trusted loopback or isolated internal network.

Operational acceptance requires (1) a live ACE-Step instance with model weights and a supported GPU, (2) source track/master rendering verified against mute/solo/inserts, (3) AI generation of a real musical excerpt and inspection of the resulting audio, (4) import of newly generated tracks without altering originals, (5) restart/persistence, failure handling, and UI A/B audition, (6) review of redistribution/model licenses and platform compatibility. Until these pass, AI Arranger/Remix are not production ready. Instrument Swap also needs dedicated stem-aware validation and must not be claimed as functioning from Cover mode alone.

Native VST3 and C++ realtime host integration remains experimental (`native_host_ready=false`).
