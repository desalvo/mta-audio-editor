# MTA Audio Editor 0.3.0 development / Sviluppo

The v0.2.0 Git tag is the stable release. Early releases use 0.3.0-rN,
starting at r1. Use VERSION, REVISION and BUILD_INFO for source identity.
Android versionCode and iOS CFBundleVersion begin at 30001 so installs can
upgrade from 0.2.0 r302 (20302) rather than downgrade.

Il nuovo motore VST3 completo (GUI, MIDI, real-time scheduling e latency
compensation) non è ancora implementato. Il codice DSP C++ rimane opzionale:
questa revisione aggiunge conversioni PCM interleaved / planar per preparare
future chiamate VST3 ProcessData, senza sostituire il motore Python.

The separate native C++ host requires additional platform-level integration,
audio parity testing, GUI threading, and real plugin validation.
