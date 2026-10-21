# OddVoices

**OddVoices** is a singing synthesizer for General American English, based on diphone concatenation with PSOLA (Pitch Synchronous Overlap Add).

This repository consists of:

- The core synthesizer, a portable C++17 library with no dependencies outside the standard library (`cpp/src/`)
- Offline analysis code in Python/NumPy/SciPy, used to convert properly tagged WAV files into .voice files (`python/oddvoices/`)
- A command-line frontend for the synthesizer that allows you to sing a MIDI file (`cpp/frontend/`)
- Three built-in voices (`voices/`):
    - **Quake Chesnokov**, a deep, dark basso profondo
    - **Cicada Lumen**, a bright and buzzy baritone
    - **Air Navier**, a soft, breathy alto

OddVoices runs on Linux, macOS, and Windows and is licensed under the Apache License.

**This project is unstable and in an early stage of development.**

## Try it online

The easiest way to use OddVoices is to use the browser version at [oddvoices.org](https://oddvoices.org/). All you need to do is upload a MIDI file and enter some lyrics.

## Command-line usage

The arguments to the `sing` executable are as follows:

    sing <voice-file> <cmudict> [-m <in-midi>] [-j <in-json>] [-l <lyrics-txt>] <out-wav>

where:

- `voice-file` is a .voice file, created with the `oddvoices-compile` Python frontend.
- `cmudict` is the path to the CMU Pronouncing Dictionary, `cmudict-0.7b`. A copy is provided with each release download.
- `in-midi` is an input MIDI file, possibly with lyrics.
- `in-json` is an input JSON file, possibly with lyrics. See `examples/example.json` for a demo.
- `out-wav` is the output WAV file.
- `lyrics-txt` is an optional path to a text file containing lyrics. If not specified, MIDI lyrics are used.

For complete instructions, see [INSTALL.md](INSTALL.md) and [docs/usage.md](docs/usage.md).

## C++ API

OddVoices works in real time. liboddvoices, the core C++ synthesizer, has a carefully designed API to separate real-time safe from non-real-time safe operations.

Here is some pseudocode:

    // Non-real-time thread:

    oddvoices::Voice voice;
    voice.initFromFile("/path/to/cicada.voice");

    oddvoices::g2p::G2P g2p("/path/to/cmudict-0.7b");
    auto phonemes = g2p.pronounce("Hello world");

    std::vector<int> segmentQueue = (
        voice.convertPhonemesToSegmentIndices(phonemes)
    );

    // Real-time thread:

    float sampleRate = 48000;
    oddvoices::Synth synth(
        sampleRate
        , &voice
        , segmentQueue.data()  // Segment queue memory
        , segmentQueue.size()  // Segment queue capacity
        , 0  // Segment queue initial starting point
        , segmentQueue.size()  // Segment queue initial size
    );

    float noteDuration = 0.5;
    synth.noteOn(noteDuration);
    synth.setTargetFrequency(220);

    for (int i = 0; i < numFrames; i++) {
        out[i] = synth.process();
    }

For more info, see `cpp/src/liboddvoices.hpp` and `cpp/frontend/sing.cpp`.

## Creating a voice

OddVoices is designed to make voice creation relatively easy. Currently, only about 30-60 minutes of voice recording are needed, best sung by a trained singer.

See [docs/creating_a_voice.md](docs/creating_a_voice.md) for full instructions.

## Copyrights

OddVoices is copyright (c) 2021 Nathan Ho and licensed under the Apache-2.0 License. See `LICENSE` for more information.

All files in the `voices/` directory are in the Public Domain.

Midifile is copyright (c) 1999-2018 Craig Stuart Sapp, and licensed under the BSD 2-Clause License.

The CMU Pronouncing Dictionary is copyright (c) 1993-2015 Carnegie Mellon University, and licensed under the BSD 2-Clause License.

Catch2 is distributed under the Boost Software License 1.0.
