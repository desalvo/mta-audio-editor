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
