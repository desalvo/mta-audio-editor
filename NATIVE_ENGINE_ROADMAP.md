# Native host status / Stato host nativo

The r300 audio_core is a separate tested C++20 PCM meter, **not a VST3 host**.
The existing Pedalboard VST3 path still renders offline. No original plug-in GUI, realtime MIDI, latency compensation or VST3 Master support is claimed.

Linux CI targets Debian/Ubuntu `.deb` and RedHat/Fedora `.rpm`, x86_64 and arm64, using native runners. Dependencies and package installation must be validated on supported target distros; CI packaging alone is not certification.

For a full host: isolate untrusted plug-in processes; design the audio callback scheduler and IPC; implement Steinberg VST3 processor/controller/state/event interfaces; bridge original native editor windows; add PDC, parameter automation and track/Master integration; prove crash recovery; run native integration tests with real VST3s.

No bulk Python-to-C++ rewrite has been performed: prioritize profiling before moving hot paths, and keep FastAPI/web/mobile behavior stable.

---

Il modulo C++20 implementa solamente il calcolo peak/RMS PCM con fallback Python. Non è ancora un host VST3 nativo. Il rendering VST3 resta su Pedalboard e l'audio in tempo reale richiede una fase successiva. I pacchetti Linux sono configurati in CI ma da convalidare su distribuzioni reali.
