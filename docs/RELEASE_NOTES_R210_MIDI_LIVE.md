
## r210 benchmark provenance follow-up — 21 October 2026

Implemented: Audio-to-MIDI benchmark file reports now record SHA-256 hashes and exact byte lengths of both local MusicResult inputs. This supports reproducibility but does not certify real neural inference or reviewed reference labels. Offline regression: **73 passed, 0 failed, 9 skipped** (requires externally reviewed GM assets/core). The controlled full suite has not been rerun and prior GitHub-request governance blocker is unresolved. No real checkpoint inference, native/browser acceptance or musical listening was performed. No production server changes and no Git operations. **The three macroareas are not signed off; software completion cannot be certified yet.**

# MTA Audio Editor 0.3.0-r210 - MIDI live / hardware / host transport

## IT

Monitoring VSTi a transport fermo con tastiera sullo schermo o ingresso MIDI, bus separato nativo C++ oppure WebSocket server/browser, selezione delle porte, Panic e pulizia delle sessioni. Uscita hardware VSTi/hardware/entrambi, note e controlli, MIDI Clock 24 PPQ/Start/Continue/Stop/Song Position, chase al seek. RtMidi nelle app native e Web MIDI con consenso del browser. Le porte sono preferenze locali per utente/progetto. Il bridge nativo serializza i messaggi e cancella le note in attesa prima di Panic.

Il runtime compilato Pedalboard/JUCE 0.9.26+mta1 comunica BPM decimali, firma metrica, campioni, secondi, PPQ, inizio battuta e stato play/pausa/loop ai VST, anche nel rendering offline, preview e bounce. RPM/DEB, Docker e workflow nativi costruiscono il runtime durante il packaging, mai all'avvio. Il motore corrente rimane disponibile; per monitoring/live host si seleziona C++.

Sono preservati tutti i file dell'archivio cumulativo precedente. Nessun incremento della revisione e nessun commit/push/tag/release. Esiti in validation/r210-midi-live-result.json. Restano le prove su dispositivi fisici e sul server di produzione. Griglia statica supportata; mappe adattive/a zone e acquisizione audio di strumenti hardware non sono incluse.

## EN

Add stopped-transport VSTi monitoring from on-screen keys or MIDI input, using a dedicated native C++ or server/browser WebSocket audition bus. Add local hardware MIDI routing, controls, optional 24 PPQ clock/transport messages, seek chase and Panic. Native output is serialized and bounded so delayed notes cannot overtake Panic. Hardware ports are local user/project preferences; external audio is not captured in exports.

Build the pinned Pedalboard/JUCE host extension during native/server packaging. Decimal BPM, static meter, sample/second/PPQ/bar position and play/pause/loop context reach VST instruments and effects, including exports/previews/bounces. Current engine remains optional; live monitoring requires C++. Preserve the entire previous cumulative project, fixed r210 identity and all prior development. See the validation report for actual results, environment exclusions and remaining physical/production acceptance.
