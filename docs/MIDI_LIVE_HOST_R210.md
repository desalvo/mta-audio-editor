> Aggiornamento / Current implementation: vedere / see VST3_COMPLETION_R210.md. Le limitazioni dei checkpoint riportati sotto sono superate ove indicato nel documento aggiornato.

# MIDI live and VST host timing - 0.3.0-r210

## Building the runtime

The host keeps the existing Pedalboard parameter/state/editor API. MTA adds a JUCE AudioPlayHead to the pinned Pedalboard VST3 wrapper and updates it on every processed block. Source: native/host_transport/MtaHostTransport.h and scripts/patch_vst3_runtime.py. Upstream: https://github.com/spotify/pedalboard, immutable commit 05e8f0b3c4851e77485d7e842dc0355b44106471 (0.9.26), including its pinned submodules. Pedalboard and JUCE retain their original licenses, including GPLv3; the wheel contains upstream license notices. The MTA extension and exact reconstruction scripts are included in this cumulative source archive. No third-party plugin binaries are redistributed.

Build on the target OS, CPU and Python ABI, never on application startup:

    python scripts/build_vst3_runtime.py --wheel-dir /external/build-cache/host-wheels --install
    python -c "from pedalboard import VST3Plugin; assert hasattr(VST3Plugin, '_mta_set_transport')"

On Debian/Ubuntu the build requires Git, CMake, C++, make, pkg-config, ALSA/freetype/X11 development packages (see Dockerfile). On EL10 use the corresponding *-devel packages listed in server-native-runtime-validation.yml. Windows uses the Visual Studio C++ toolchain; macOS uses Xcode command-line tools. Wheels are specific to the interpreter and architecture. The package is identified as 0.9.26+mta1, compatible with the application's pedalboard==0.9.26 requirement. Application revision stays 0.3.0-r210. The build manifest hashes the extension and wheel; runtime install smoke tests assert the transport API.

Server RPM/DEB staging builds the wheel before downloading the remaining binary dependency closure, then locks all hashes. Docker has a separate builder stage. Native release workflows build/install before freezing. A build failure must fail the package build; installing the unmodified PyPI wheel is not an equivalent transport runtime.

## Behaviour and limits

Use the static project/metronome BPM and time signature. All VSTi/effect nodes receive sample-domain timing; source-domain tempo compensates the final project stretch. Seek repositions PPQ and resets voices; pause freezes sample advance. Offline mix and direct project preview carry the same settings. Adaptive/zoned metronome tempo maps are not synthesized. Loop flags are context metadata, not an implementation of transport looping.

Interactive monitoring is separate from the project notes and does not save transient input. Save MIDI persists recorded draft notes. Native RtMidi callbacks only enqueue bounded messages; plugin processing and port output run outside the audio callback. A shared output handle supports exclusive-open Windows drivers. Native hardware playback follows the device sample counter, sampled in a separate scheduler. Web playback uses Web MIDI output timestamps with 32 ms lookahead. MIDI Clock is 24 PPQ with Start/Continue/Stop/Song Position; software, bridge and OS jitter remain.

Web monitoring uses authenticated same-origin WebSockets with 1024-frame stereo PCM, bounded buffering, request/message limits and shared VST session quotas. It requires WebSocket forwarding through HAProxy; browser input/output requires HTTPS and Web MIDI permission. Native apps use RtMidi where Web MIDI is absent. On-screen keys need no device permission. Server audio includes network latency, displayed alongside queued audio. This is not a hard-real-time guarantee.

Hardware output is a local user/project preference; it is not embedded as a server device name or sent to the hypervisor. Hardware-only tracks export silence in audio and remain exportable as MIDI. External audio needs separate capture. Panic can affect tracks sharing an output/channel. Stop, seek, disconnect and shutdown release voices and cancel queued output. Physical Windows/macOS/Linux ports and production HAProxy must still be tested on the actual machines.

## Validation

Tests cover actual Surge XT monitoring over authenticated WebSocket, nonzero PCM from received notes, project-note isolation, channel-message validation, ownership/Origin rejection, cleanup, compiled decimal BPM/7-8/PPQ/seek/pause context, deterministic hardware scheduling/chase/clock using a virtual output, and browser clip mapping against the backend scheduler. Actual Chromium verifies the editor, monitoring keys, streamed audio and stop. Detailed results are in validation/r210-midi-live-*.xml and the cumulative report. Virtual ports and a null output device do not certify physical latency or every third-party plugin.
