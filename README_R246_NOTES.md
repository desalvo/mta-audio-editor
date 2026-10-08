# r246 — Metronome and crash-safety implementation notes

- Metronome generator supports standard (fixed), marker zones and adaptive. Each zone resets pulse phase and bar accents.
- Adaptive sensitivity persists in the project and affects interval smoothing. No external AI model is embedded; such a model would require separate validation.
- Context action regenerates Chords or Click according to the stored mode. Zone is identified from transport position; **zone-specific audio-only rendering remains a future optimization** (currently atomically renders whole click track).
- Track audio renders are staged in separate temporary WAVs and atomically swapped upon success. Metadata is also saved atomically. A sudden interruption between replacing audio and metadata can temporarily leave the old metadata with new audio; complete two-file atomic transactions require a journal/snapshot system.
- Show Markers overlays text and vertical marker lines on the timeline. The transport buttons use icons with tooltips.
