# MTA proprietary format research

Version: 0.2.0-70

This document records only findings demonstrated against the current four-file stock M-Live corpus. It is intentionally conservative: a field is not treated as a writable contract until round-trip output has been validated on real M-Live/Merish hardware.

## Corpus

The accumulated research corpus contains six independent stock MTA files:

- Rita Ora - Ask & You Shall Receive
- Madonna - Into The Groove
- Earth Wind & Fire - Boogie Wonderland
- Michael Jackson - Man In The Mirror
- Katrina And The Waves - Walking on sunshine
- Rihanna - Don't Stop The Music

The current Library-backed binary pass has direct access to the latter four files; findings already demonstrated on Rita Ora and Madonna remain part of the accumulated corpus record.

Copyrighted MTA/audio samples are not shipped with the project. Tests use synthetic fixtures reproducing only the verified structures.

## Container and attachments

MTA files in the corpus are Matroska/EBML containers containing MP3 stereo 44.1 kHz audio streams plus four attachment streams:

- ORG SYL: `ID3 LYRICS COLORS MIDITK(+MARKER) CHORDS`
- MOD SYL
- ORG `MtxInfoData` XML
- MOD XML

Across the verified samples inspected for attachments, ORG and MOD copies are byte-identical. FFmpeg may emit EBML boundary warnings on stock files, so `app/mta_reverse.py` includes a conservative FileData fallback based on attachment sizes reported by FFprobe.



## Matroska Cues and media transport — resolved

The media transform is now demonstrated, not hypothetical. Across the four stock files currently available for byte-level verification, every byte from the first Matroska `Cluster` through EOF is transformed as:

```text
plain[i] = stored[i] XOR key[i mod 984]
stored[i] = plain[i] XOR key[i mod 984]
```

where `i=0` is the first byte of the first Cluster. The phase does **not** reset at Cluster or Cue boundaries. The recovered key is 984 bytes long and has SHA-256:

```text
bcb30443707bdc8b651c1a58aa4152438ce5a6632cc98b294501eb08adbb3547
```

The complete period was solved from canonical Matroska known plaintext (`Cluster`, `Timecode`, `SimpleBlock`, track numbers, flags and MP3 sync/header fields), not from a decrypted reference file. Applying the stream through EOF produces canonical Matroska in all four files; FFmpeg then reads every audio packet normally.

Verified packet counts are 8979 (Earth Wind & Fire, 14 tracks), 9111 (Katrina, 12), 10200 (Michael Jackson, 14) and 10798 (Rihanna, 10).

### Exact Cluster grammar

A full Cluster contains ten MP3 frame-times for every audio track, ordered frame-major. Each `SimpleBlock` contains exactly one MPEG-1 Layer III frame and has seven bytes of Matroska overhead:

```text
A3 <2-byte EBML size> <track VINT> <signed int16 relative timecode> 80 <MP3 frame>
```

Relative block timecodes are exactly:

```text
0, 144, 288, 432, 576, 720, 864, 1008, 1152, 1296
```

The absolute Cluster timecode is reproduced exactly by:

```python
cluster_timecode(i) = floor(i * (800000000 / 555513) + 1/16)
```

`TimecodeScale = 181392 ns`; each audio track has `DefaultDuration = 26122448 ns`.

### Exact MP3 padding schedule

Packet zero is the unpadded 1044-byte `Info` frame. Subsequent CBR 320 kbit/s / 44.1 kHz frames use:

```python
padding = [0]
state = 4
for each later frame:
    state += 44
    if state >= 49:
        padding.append(1)
        state -= 49
    else:
        padding.append(0)
```

Thus MP3 frames are 1044/1045 bytes and SimpleBlocks are 1051/1052 bytes. All tracks in all four verified files use the same sequence.

The final partial Cluster uses the minimal EBML size VINT. This resolves the previous Katrina one-byte end-of-file discrepancy: predicted Cluster sizes now match every Cluster in every verified file exactly.

### Cues

Cue count is exactly `ceil(packet_count_per_track / 40)`. Cue `n` points to Cluster `4*n`, with `CueClusterPosition` relative to Segment data start. All Cue times and positions match the deobfuscated Cluster stream exactly.

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

Examples such as `BOOGIE WONDERLAND` yield positions `3, 6, 9, 12, 15, 16`, matching progressive advancement through the non-space characters of the lyric line/segment. The value `127` is a display-page reset control rather than a character position. Across the four stock files it follows completion of the previous displayed lyric line and immediately precedes the first lyric record of the next display page.

This indicates that a COLORS record is an event in the karaoke highlight stream rather than a fixed-rate time sample.

## MIDITK

MIDITK is now demonstrated to be an obfuscated Standard MIDI File, not a separate proprietary event language.

After the shared keystream/global XOR and an additional XOR `0x30`, the verified stock payloads reconstruct byte-exact MIDI files beginning with:

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

`NoteOn` is a semicolon-separated one-second source-activity mask. Across 4 songs, 50 tracks and 12,654 bins, decoded-audio RMS reconstructs more than 99.8% of the bits with per-track separation; residual disagreements cluster at activity boundaries and very low-level material, consistent with pre-encode/source activity rather than a fixed post-MP3 threshold.

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


## Xing/Info frame — resolved

The first MP3 packet of every track is an unpadded 1044-byte `Info` frame matching the FFmpeg/libavformat MP3 muxer layout:

```text
36..39    "Info"
40..43    flags = 0x0000000f
44..47    frame count (excluding Info)
48..51    total MP3 bytes (including Info)
52..151   Xing TOC[100]
152..155  quality
156..     encoder string ("Lavc58.13" in the verified corpus)
177..179  packed encoder delay/padding
184..187  music length
188..189  music CRC
190..191  tag CRC
```

`Info.frames = packet_count - 1`; `Info.bytes == music length == sum(all MP3 frame bytes including Info)`.

The TOC is the FFmpeg/LAME-style 400-entry sampling-bag algorithm and is fully determined by frame sizes.

CRC fields are exact:

```text
music CRC = CRC-16/ANSI reflected, polynomial 0xA001, initial 0,
            over every musical MP3 frame (Info excluded)

tag CRC   = same CRC over Info-frame bytes 0..189
```

Recalculation reproduces the stock CRCs exactly.

## SeekHead and Cues writer formulas

Each Seek entry consists of a fixed 7-byte `SeekID` element plus a minimal-width `SeekPosition`; with an `n`-byte position the complete `Seek` entry is `13+n` bytes.

For the verified value ranges a CuePoint is:

```text
11 + byte_length(CueTime) + byte_length(CueClusterPosition)
```

bytes long. Positions are relative to Segment data start. Segment size is exactly `file_size - segment_data_offset`, reaching EOF in all four files.

These formulas plus the exact Cluster-size model are sufficient to solve all index offsets by fixed-point iteration when writing a new container.

## Analysis completion status

For the verified four-file stock corpus, the stored MTA format is now reverse-engineered sufficiently for deterministic reading and authoring. COLORS 127 is a display-page reset control and NoteOn is a one-second pre-encode/source activity mask. The exact private source-activity detector is not observable from a final lossy MP3 and is not an unresolved on-disk primitive. See `MTA_FORMAT_FINAL_SPEC.md`.
