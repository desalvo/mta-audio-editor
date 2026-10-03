# Data model and persistence

## Project

`Project` is the persisted editor aggregate. Important fields include:

```text
id
owner_user_id
shared_with_user_ids[]
title
artist
bpm
key
target = MTA8 | MTA16
mta_device_profile = auto | merish5_xynthia2 | bbeat_divo | mlive_mta16_default | merish5_plus_mta16 | generic
tracks[]
markers[]
lyrics[]
chords[]
preserved_attachments[]
master_volume_db
master_inserts[]
auto_mix_enabled
auto_mix_style
auto_mix_snapshot
base_bpm
pitch_semitones
realtime_meter_enabled
render_preview_enabled
follow_playback_enabled
timeline_zoom_px_per_sec
export_format
```

## Track

A Track stores editor/mixer state and references one working source file:

```text
id
name
type
mta_slot
filename
duration_ms
volume_db
pan
mute
solo
color
clips[]
inserts[]
```

Track types are constrained to the application's known MTA/editor taxonomy such as drums, bass, guitars, keyboards, orchestra, winds, melody, click, choirs and other. `mta_slot` is an optional persisted preferred output slot (1-8 for MTA8, 1-16 for MTA16); `null` means Auto/profile-driven placement. Confirming an export mapping updates the corresponding track slot preference.

## Clip

A Clip is a non-destructive timeline reference:

```text
id
source_start_ms
source_end_ms
timeline_start_ms
```

Duration is `max(0, source_end_ms - source_start_ms)`.

## Timeline events

Markers:

```text
time_ms
label
```

Lyrics:

```text
time_ms
text
```

Chords:

```text
time_ms
chord
```

Global ripple/delete operations update these event positions together with audio clips.

## InsertPlugin

Each insert has:

```text
id
plugin
preset
enabled
params{}
```

A track or master chain contains at most 16 inserts. Plugin type and parameter schema are server-controlled.

## Auto Mix snapshot

The snapshot stores exact pre-Auto-Mix state:

```text
tracks[track_id]:
  volume_db
  pan
  inserts[]

master_volume_db
master_inserts[]
```

This is what makes Auto Mix reversible.

## Authentication database

SQLite tables cover:

- users;
- sessions;
- email tokens;
- SMTP configuration.

Passwords are stored only as password hashes. Session tokens are stored as hashes. TOTP/SMTP secrets are sealed before persistence.

## Filesystem relationship

`project.json` references working filenames relative to the project's controlled directories. It never stores arbitrary absolute filesystem paths.

`audio/` contains working track sources. `originals/` preserves uploaded originals. `attachments/` preserves MTA attachments and analysis sidecars.

## Ownership and sharing

`owner_user_id` is authoritative ownership.

`shared_with_user_ids` is a set-like validated list; duplicate IDs are normalized away.

On full-project archive import:

- a new project ID is allocated;
- importer becomes owner;
- share list is cleared.

This prevents imported archives from granting access to unrelated local users.

## MTA device profile

`mta_device_profile` is persisted with the project and controls Click/Melody export placement:

```text
merish5_xynthia2: MTA8 Melody 7, Click 8
bbeat_divo:       MTA8 Click 7, Melody 8
mlive_mta16_default: MTA16 Click 1, Melody 9
generic:          manual/non-device-specific mapping
auto:             resolves to the current target default
```

The export layer may insert silent intermediate streams to preserve a physical slot number. The profile is a project preference; a configured export request can override it for one export.

## Waveform cache

Tracks also persist normalized waveform peaks plus a revision/signature. The UI can display cached peaks immediately when reopening a project. Missing or stale peaks are regenerated asynchronously and saved back into the project. Playback never depends on waveform availability.

## Native project binding

Desktop-native save-path bindings are stored outside `project.json` in the native application data directory so a project can remain portable while the local app remembers which archive path is associated with the project ID.
