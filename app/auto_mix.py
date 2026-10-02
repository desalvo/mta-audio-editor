"""Conservative rule-based Auto Mix wizard.

Auto Mix is reversible. Enabling it snapshots user mix settings, then applies a
small allow-listed set of track-type rules and a master preparation chain.
Disabling restores the snapshot exactly.
"""
from __future__ import annotations

import uuid

from .models import AutoMixSnapshot, AutoMixTrackSnapshot, InsertPlugin, Project


def _fx(plugin: str, preset: str) -> InsertPlugin:
    return InsertPlugin(id=f"automix_{uuid.uuid4().hex[:10]}", plugin=plugin, preset=preset)


def _track_rules(track_type: str, style: str) -> tuple[float, list[InsertPlugin]]:
    gentle = style == "gentle"
    rules = {
        "drums": (-5.0 if gentle else -4.0, [_fx("graphic_eq_32", "drums-punchy"), _fx("compressor", "drums")]),
        "bass": (-6.0 if gentle else -5.0, [_fx("graphic_eq_32", "bass-warm"), _fx("compressor", "bass")]),
        "guitars": (-8.0 if gentle else -7.0, [_fx("graphic_eq_32", "guitar-clarity"), _fx("compressor", "moderate")]),
        "keyboards": (-9.0 if gentle else -8.0, [_fx("graphic_eq_32", "piano-natural"), _fx("stereo_imager", "wide")]),
        "orchestra": (-9.0 if gentle else -8.0, [_fx("room_ambience", "studio-a")]),
        "winds": (-8.0 if gentle else -7.0, [_fx("graphic_eq_32", "flat-32"), _fx("compressor", "moderate")]),
        "melody": (-7.0 if gentle else -6.0, [_fx("denoise", "light"), _fx("graphic_eq_32", "vocals-presence"), _fx("compressor", "vocal"), _fx("reverb_lexicon", "lexicon-vocal-plate")]),
        "click": (-14.0 if gentle else -12.0, []),
        "choirs": (-9.0 if gentle else -8.0, [_fx("compressor", "moderate"), _fx("reverb_lexicon", "lexicon-ambient"), _fx("stereo_imager", "wide")]),
        "other": (-9.0 if gentle else -8.0, [_fx("compressor", "moderate")]),
    }
    return rules.get(track_type, rules["other"])


def _pan_tracks(project: Project, style: str) -> None:
    # Keep bass, kick/drums, lead melody and click centered. Spread repeated
    # harmonic/support parts conservatively for headroom and separation.
    by_type: dict[str, list] = {}
    for track in project.tracks:
        by_type.setdefault(track.type, []).append(track)
    amount = 0.22 if style == "gentle" else (0.45 if style == "live" else 0.35)
    for kind in ("guitars", "keyboards", "orchestra", "winds", "choirs", "other"):
        items = by_type.get(kind, [])
        if len(items) == 1:
            items[0].pan = 0.0 if kind in {"other", "winds"} else amount * 0.35
        else:
            for idx, track in enumerate(items):
                track.pan = (-amount if idx % 2 == 0 else amount) * (1.0 if idx < 2 else 0.7)


def enable_auto_mix(project: Project, style: str = "balanced") -> Project:
    if project.auto_mix_enabled:
        # Re-apply a different style from the original snapshot rather than
        # compounding rules on top of previous Auto Mix output.
        disable_auto_mix(project)
    project.auto_mix_snapshot = AutoMixSnapshot(
        tracks={
            track.id: AutoMixTrackSnapshot(
                volume_db=track.volume_db,
                pan=track.pan,
                inserts=[item.model_copy(deep=True) for item in track.inserts],
            )
            for track in project.tracks
        },
        master_volume_db=project.master_volume_db,
        master_inserts=[item.model_copy(deep=True) for item in project.master_inserts],
    )
    for track in project.tracks:
        target_db, effects = _track_rules(track.type, style)
        track.volume_db = target_db
        track.inserts = track.inserts + effects
    _pan_tracks(project, style)
    project.master_volume_db = -1.0 if style == "live" else 0.0
    preset = {"balanced": "balanced", "studio": "clear", "live": "live-pa", "gentle": "warm"}[style]
    project.master_inserts = project.master_inserts + [
        _fx("mastering_wizard", preset),
        _fx("maximizer_loudness", "transparent" if style in {"balanced", "gentle"} else "live"),
    ]
    project.auto_mix_enabled = True
    project.auto_mix_style = style
    return project


def disable_auto_mix(project: Project) -> Project:
    snapshot = project.auto_mix_snapshot
    if snapshot:
        for track in project.tracks:
            saved = snapshot.tracks.get(track.id)
            if saved:
                track.volume_db = saved.volume_db
                track.pan = saved.pan
                track.inserts = [item.model_copy(deep=True) for item in saved.inserts]
            else:
                track.inserts = [item for item in track.inserts if not item.id.startswith("automix_")]
        project.master_volume_db = snapshot.master_volume_db
        project.master_inserts = [item.model_copy(deep=True) for item in snapshot.master_inserts]
    else:
        for track in project.tracks:
            track.inserts = [item for item in track.inserts if not item.id.startswith("automix_")]
        project.master_inserts = [item for item in project.master_inserts if not item.id.startswith("automix_")]
    project.auto_mix_enabled = False
    project.auto_mix_snapshot = None
    return project
