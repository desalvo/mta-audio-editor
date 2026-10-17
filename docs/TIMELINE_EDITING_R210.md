# Timeline editing, stem names and master fades — r210

See [independent metronome grids and musical delay](METRONOME_GRID_AND_MUSICAL_DELAY_R210.md) for the subsequent grid controls and per-track unit selector.

Version remains **0.3.0-r210**. This cumulative package preserves the preceding admin AI queue, SMTP/social login, account lifecycle and email/TOTP MFA changes.

## Segments and stems

Stem names use the output instrument/voice name without the source track prefix. Case-insensitive collisions receive ` 2`, ` 3`, etc. Selective reprocessing identifies derived tracks by source ID and stem key, preserving their mixer settings without overwriting an unrelated track with the same name.

With **Select**, click a segment to select it. Ctrl/Cmd/Shift+click toggles additional segments, including segments on other tracks. Dragging a selected segment moves the selection together; Left/Right moves it by 10 ms with snap off, or one musical grid step with snap enabled. Range and Split retain their own tools. Copy/Cut/Remove act on selected segments in Select mode. Paste refuses overlapping placements.

**Snap** is functional and persistent: Off, Beats, Bars. The musical pulse follows the existing MTA BPM convention; the signature numerator groups pulses into bars. Adaptive beat maps are used where present. The **Magnet** toolbar toggle attracts segment edges within eight screen pixels. It takes priority over the musical grid when enabled. Same-track obstacles clamp movement, preventing overlap or jumping through another segment; segments on parallel tracks may overlap normally. Existing overlapping projects remain loadable, but editing cannot introduce or reposition an overlap.

Moving segments and changing a track delay invalidate the audio preview cache. Active WebAudio playback is rebuilt at the transport position; edits made while paused are applied upon resume. Delay is non-destructive and affects real playback and exports. Negative delays crop only the audible portion before project zero.

## Metronome

The track context menu includes **Insert metronome at transport position**. The settings dialog accepts an insertion timestamp and 0–64 pre-roll bars. If pre-roll would precede zero, the project is extended at the beginning: audio clips and synchronized lyrics/chords/markers are shifted together. Files remain unmodified. Failure during click generation restores the previous project positions. The metronome remains a single generated track.

**R** regenerates a selected metronome or generated chords track when focus is outside text inputs. The shortcut is also shown in the context menu, in the current language.

## Trim and fades

**LTrim** and **RTrim** remove leading or trailing silence from the audible mix, with a -120 dBFS detection threshold. Silence is detected before master fades, preserving quiet fade tails. Muted/solo state and track processing are respected. Edits change clip boundaries and synchronized event positions, never source audio. Intentional empty tracks persist without restoring a deleted full-source clip. The retained duration is stored in the project.

**Fade In / Out** opens project-level master automation. Enable the option and configure each side in milliseconds; zero disables that side. The two linear envelopes multiply when their durations overlap. WebAudio schedules the master gain at playback and seeks, including project tempo changes. WAV/FLAC/MP3 and MTA slot exports apply the corresponding master envelope before project tempo/pitch transformation. Fades are saved in project files and portable archives. MTA exports contain already-faded slot audio and annotate the original fade settings in the metadata attachment.

## Verification limits

Automated regression includes real FFmpeg audio for delay, fade amplitudes and silence boundaries; model persistence; pre-roll extension/rollback endpoints; overlap guards; Node execution of snap/magnet rules and pointer selection, group drag and cancellation. The report under `validation/` records final results.

Manual checks remain necessary on the installed Windows/macOS native applications and the deployed web server: actual pointer interaction at different zoom levels, audible delay changes during playback/pause, musical snap, pre-roll phase, trim undo and master fades at the transport start/seek/export. This package does not certify server GPU billing or ROCm inference hardware.
