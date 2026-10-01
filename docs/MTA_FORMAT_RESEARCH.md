# MTA proprietary format research

Version: 0.2.0-12

This document records only findings demonstrated against the current four-file stock M-Live corpus. It is intentionally conservative: a field is not treated as a writable contract until round-trip output has been validated on real M-Live/Merish hardware.

## Corpus

The current research corpus contains four independent stock MTA files:

- Rita Ora - Ask & You Shall Receive
- Madonna - Into The Groove
- Earth Wind & Fire - Boogie Wonderland
- Michael Jackson - Man In The Mirror

Copyrighted MTA/audio samples are not shipped with the project. Tests use synthetic fixtures reproducing only the verified structures.

## Container and attachments

MTA files in the corpus are Matroska/EBML containers containing MP3 stereo 44.1 kHz audio streams plus four attachment streams:

- ORG SYL: `ID3 LYRICS COLORS MIDITK(+MARKER) CHORDS`
- MOD SYL
- ORG `MtxInfoData` XML
- MOD XML

In all four verified samples ORG and MOD copies are byte-identical. FFmpeg may emit EBML boundary warnings on stock files, so `app/mta_reverse.py` includes a conservative FileData fallback based on attachment sizes reported by FFprobe.

## SYL / ID3v2.3

The `.syl` attachment is a complete ID3v2.3 tag. Standard frames observed include title, artist, BPM, key, length, publisher, composer, genre, copyright, year, album and ISRC.

After the standard frames/padding, stock files contain:

- `DELTABEGIN ... DELTAEND`
- `LYRICSBEGIN ... LYRICS200`
- `COLORSBEGIN ... COLORS200`
- `MIDITKBEGIN ... MIDITK200`
- `CHORDSBEGIN ... CHORDS200`

The wrapper resembles Lyrics3-style length framing, but its binary payloads are M-Live-specific.

## Shared keystream

The proprietary sections share a 256-byte XOR keystream. COLORS exposes the full keystream directly through byte 0 of its first 256 normal records. Across all verified stock files the recovered sequence is the same and is a permutation of all byte values `0x00..0xFF`.

Observed phase relationships:

- COLORS byte `(record_index, byte_index)`: `(record_index - 17 * byte_index) mod 256`
- LYRICS / CHORDS flat payload byte: `239 * payload_offset mod 256`
- MIDITK flat payload byte: `239 * (payload_offset - 3) mod 256`

Since `239 == -17 (mod 256)`, these sections use the same underlying phase progression.

## LYRICS and CHORDS

After removing the 3-byte common binary prefix and applying the shared keystream/global XOR, records have the verified structure:

```text
LF d d RS d d 'm' <text-XOR-0x30> =:k NUL <next-minute>
```

The four decimal digits encode centiseconds within the current minute:

```text
centiseconds = d1*1000 + d2*100 + d3*10 + d4
time_ms = minute_block*60000 + centiseconds*10
```

The final byte in the delimiter is the minute block used by the following record. Text/chord bytes use an additional XOR `0x30` transform.

On all four corpus files the decoded times are monotonic and yield readable lyric/chord strings.

## COLORS

The verified physical format is:

```text
3-byte binary prefix
+ N records of 15 bytes
```

The final physical record is a distinct terminator and is excluded from normal highlight events.

After de-obfuscation, every normal record has the corpus-verified layout:

```text
LF d d RS d d 'm' p p p '=' ':' 'k' NUL <next-minute>
```

`dddd` uses the same centisecond/minute timing model as LYRICS/CHORDS. `ppp` is a decimal progressive highlight position:

```text
position = p1*100 + p2*10 + p3
```

Examples such as `BOOGIE WONDERLAND` yield positions `3, 6, 9, 12, 15, 16`, matching progressive advancement through the non-space characters of the lyric line/segment. The value `127` appears as a special sentinel in the stock corpus; its exact writer semantic is intentionally not asserted yet.

This indicates that a COLORS record is an event in the karaoke highlight stream rather than a fixed-rate time sample.

## MIDITK

MIDITK is now demonstrated to be an obfuscated Standard MIDI File, not a separate proprietary event language.

After the shared keystream/global XOR and an additional XOR `0x30`, all four stock payloads reconstruct byte-exact MIDI files beginning with:

```text
MThd
format 0
1 track
PPQ 480
MTrk
```

The MTrk declared length matches the reconstructed track bytes. Standard MIDI meta-events include tempo and marker events such as `Intro`, `Verse`, `Chorus`, `Bridge`, `Special`, `Coda` and `Fine` depending on the song.

`decode_miditk_to_midi()` reconstructs the exact MIDI bytes. During attachment analysis the verified result is also written as a `.miditk.mid` sidecar. The analysis report inventories format, PPQ, track length, tempo events and marker timestamps, and the application exposes the first verified sidecar through `GET /api/projects/{pid}/mta-miditk`.

## MtxInfoData XML

The XML attachment is parsed defensively using `defusedxml`. Verified fields include Identity, General data and audio-track metadata.

`NoteOn` is a semicolon-separated 0/1 vector whose length tracks `DurataSec` at approximately one entry per second (with an endpoint convention difference in some files). The exact energy threshold used by the original writer remains unknown.

## Read/write policy

Current production policy:

- read and report demonstrated structures;
- preserve unknown/undocumented payloads byte-for-byte;
- allow exact MIDITK reconstruction for analysis/export helpers;
- do not rewrite proprietary stock SYL fields based only on inferred semantics;
- do not claim bit-perfect Merish/M-Live writer compatibility until controlled round-trip files are accepted by target hardware.

## Next research steps

The most useful next evidence is a controlled pair of MTA files for the same song with exactly one modification at a time, for example:

- one changed lyric syllable;
- one shifted lyric timestamp;
- one changed chord;
- one changed section marker;
- one changed highlighting boundary/color/state.

Such pairs can identify the remaining COLORS sentinel semantics and provide writer validation with minimal ambiguity.
