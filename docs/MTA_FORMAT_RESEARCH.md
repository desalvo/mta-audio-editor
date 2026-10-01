# MTA proprietary format research

Version: 0.2.0-29

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


## Matroska Cues and obfuscated media transport

The six-file reverse-engineering corpus now shows a stronger split between the
canonical Matroska index and the media payload. `SeekHead` still contains a
normal `SeekID=1F43B675` entry for Cluster and `Cues` contains normal
`CueClusterPosition` values. Those positions are therefore trustworthy byte
boundaries even though the data stored there is not canonical EBML.

On the four corpus files currently available in the project Library (Rihanna,
Katrina And The Waves, Michael Jackson and Earth Wind & Fire), the first cue
position exactly matches the Cluster position advertised by SeekHead. The first
four bytes at that position are always:

```text
0f b2 f7 b0
```

instead of the Matroska Cluster ID `1f 43 b6 75`. FFmpeg reports the same
non-canonical EBML boundary. This is no longer treated as a damaged SeekHead:
the readable Cues provide hundreds of successive media boundaries.

Additional cross-file evidence is especially useful: Michael Jackson and Earth
Wind & Fire both expose 14 MP3 tracks and have the same per-cluster spacing for
the overlapping part of the files. When their media regions are aligned to the
first cue, the first 16 bytes at corresponding cue boundaries are byte-identical
for the first 32 checked clusters (and the relative boundary offsets also
match). The encrypted/obfuscated bytes therefore behave deterministically with
respect to the media-stream position/layout and are not consistent with random
per-file IV data at each cluster boundary.

The transform is still deliberately described as **non-canonical / obfuscated
media transport**, not as a proven cipher. The sparse/local differences between
aligned files and long equal runs argue against an ordinary avalanche-style
block-cipher mode over the whole region, but the exact transform and any key or
PRNG state are not yet demonstrated.

`inspect_cluster_transport()` now records the SeekHead Cluster target, Cues,
cluster spans and observed prefixes without attempting speculative decryption.
This gives the next stage of the reverse engineering stable known boundaries.

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

## Cluster transport: corpus comparison update (0.2.0-29)

A cross-file comparison of the four locally verified stock MTA files (10, 12 and 14 audio tracks) adds several useful constraints without claiming a decryption algorithm.

- The first media boundary always starts with ciphertext bytes `0f b2 f7 b0`, while later Cue-selected media boundaries use different prefixes.
- In the first media block, bytes 7..62 are identical across the 10-, 12- and 14-track files; only bytes 4..6 differ in the first seven bytes. This strongly suggests a stable structural/encoder prefix after a size-dependent header transform.
- The first media spans are 420793 bytes (10 tracks), 504943 bytes (12 tracks) and 589093 bytes (14 tracks). Each additional two tracks adds exactly 84150 bytes, i.e. 42075 bytes per track for this Cue interval.
- The Matroska `TimecodeScale` is `181392 ns`, not the default 1 ms. The common Cue delta of `5760` therefore corresponds to about `1.044818 s`.
- Every audio track declares `DefaultDuration = 26122448 ns`, matching one 44.1 kHz MPEG-1 Layer III frame (`1152/44100 s`) to truncation. One frame is approximately 144 MTA timecode ticks, and 40 frames give the observed 5760-tick Cue interval.
- The first media spans follow the exact corpus relation `span = 43 + 42075 * audio_track_count`: 420793 bytes (10 tracks), 504943 (12) and 589093 (14). The following common spans similarly fit `44 + 42076*N` or `44 + 42075*N`.
- `42075/42076` bytes per track per 40-frame interval decomposes exactly as 40 Matroska `SimpleBlock` records carrying 320 kbit/s MP3 frames: a 320 kbit/s / 44.1 kHz Layer III frame is 1044 or 1045 bytes depending on the padding bit, and a normal one-frame `SimpleBlock` adds 7 bytes of Matroska overhead, yielding 1051/1052-byte records. The observed totals require 35/36 padded frames respectively.
- Comparison of two independent 14-track songs reveals an extremely strong ~14728-byte difference periodicity (`14 * 1052`). Within those periods, nearly all differences concentrate in the first 1052-byte track slot while the other 13 slots remain almost identical during the opening material. This independently supports frame-major interleaving of one `SimpleBlock` per track and per MP3 frame.
- A synthetic canonical Matroska file generated with 44.1 kHz stereo MP3 confirms the expected `Cluster -> Timecode -> SimpleBlock -> MP3 frame` grammar and the 7-byte one-frame SimpleBlock overhead, providing a concrete known-plaintext template for the next cryptanalysis step.

For two independent 14-track songs, the corresponding first media block has the same boundary offsets and very large byte-identical regions; the first block is over 90% identical, while similarity drops after musical content begins. This behavior is more consistent with a deterministic, position-sensitive, length-preserving transform than with a conventional avalanche-mode block cipher over the entire media stream.

The next targeted task is to recover the first canonical `SimpleBlock` header and MP3 frame header, then test bytewise/stream transforms separately from the 7-byte media-boundary header.
