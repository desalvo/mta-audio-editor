## 0.3.0-r15 — VST3 processor capability diagnostics and CI build gate

- Isolated lifecycle mode now probes supported 32-bit/64-bit sample formats and reported plugin latency. Values are sanitized in the Python adapter; no audio processing is enabled.
- GitHub Actions quality job now builds the standalone C++20 VST3 probe without Steinberg SDK as a regression gate.
- Added tests for capability decoding, invalid latency data and playback isolation.
- SDK-backed compilation and real plugin interoperability remain unverified. No claims of resolving remote Actions failures without corresponding logs.

## 0.3.0-r14 — Isolated VST3 diagnostic host context

- Added a stack-scoped minimal `IHostApplication` implementation with host name, interface negotiation and reference counting in the subprocess only.
- `--lifecycle` now passes that diagnostic context to `IComponent::initialize()`. Unsupported host-created objects explicitly return `kNotImplemented`.
- Added `host_context_provided` to diagnostic JSON/Python results. `native_host_ready` remains `false`.
- No playback, rendering, VST audio processing, plugin editor or automation changes.
- SDK-backed compilation and real-plugin interoperability are **not yet validated**. Some plug-ins can legitimately decline initialization.
- Preserved the r13 VST3 support manual cover titles and PDFs.

# VST3 host development status (0.3.0-r7)

The isolated `native/vst3_probe` can now optionally compile against the independently
obtained, MIT-licensed Steinberg VST3 SDK to invoke `IPluginFactory::countClasses()`.
This only enumerates the factory count; it is **not** an audio host.

```sh
cmake -S native/vst3_probe -B build/vst3-probe -DMTA_VST3_SDK_ROOT=/path/to/vst3sdk
cmake --build build/vst3-probe
```

Without `MTA_VST3_SDK_ROOT` the probe continues its safe export-only behavior.
Do not activate SDK enumeration by default; plugin code runs inside the isolated
probe process and can fail or time out.

Outstanding: OS-dependent module initialization, `IComponent` / `IAudioProcessor`
instantiation, processor/controller lifecycle, audio bus setup, `ProcessData`,
latency, MIDI, UI embedding, state persistence and process isolation. Existing
Pedalboard offline rendering is still the default; nothing here claims realtime VST3.

License and distribution: SDK not vendored; retain upstream license and notices
where required. Third-party plugins must be installed by the end user and must
not be bundled into MTA packages without explicit redistribution rights.

## 0.3.0-r10

Optional exact-CID IComponent creation diagnostic through IPluginFactory::createInstance(), followed by immediate release. No initialization, bus setup or processing. The probe is never called from realtime playback.

## 0.3.0-r11

The `--lifecycle <CID>` opt-in subprocess diagnostic attempts `IComponent::initialize(nullptr)` then calls `terminate()` only if initialization succeeded, and always releases the interface. A null host context is an intentional limitation; production host interfaces, module entry lifecycle, realtime processing and GUI integration are not implemented. `--instantiate` remains unchanged.

## 0.3.0-r12
- Isolated bus metadata interrogation after successful lifecycle initialization (audio/event buses only).
- Host context, activation, processing and GUI remain unimplemented; no changes to playback.

## 0.3.0-r13
- Optional component interface query for IAudioProcessor and IEditController.
- The processor and controller queries are diagnostic only and their result is never used in playback.
- Build against an actual Steinberg SDK and test plugin instances before claiming host readiness.
