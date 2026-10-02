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
```

## Track

A Track stores editor/mixer state and references one working source file:

```text
id
name
type
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

Track types are constrained to the application's known MTA/editor taxonomy such as drums, bass, guitars, keyboards, orchestra, winds, melody, click, choirs and other.

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
