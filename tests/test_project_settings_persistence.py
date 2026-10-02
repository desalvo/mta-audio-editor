from pathlib import Path

from app.models import InsertPlugin, Project, Track


def test_project_model_persists_working_settings_and_mix_state():
    project = Project(
        id="p",
        title="Persist",
        target="MTA16",
        follow_playback_enabled=True,
        realtime_meter_enabled=True,
        render_preview_enabled=True,
        auto_mix_enabled=True,
        auto_mix_style="studio",
        master_volume_db=-2.5,
        master_inserts=[InsertPlugin(id="m1", plugin="limiter", preset="safe-2")],
        export_panel_visible=False,
        metadata_panel_visible=False,
        timeline_zoom_px_per_sec=135,
        mixer_meta_tab="markers",
        export_format="flac",
        tracks=[
            Track(
                id="t1",
                name="Track",
                filename="track.wav",
                volume_db=-4.0,
                pan=0.25,
                mute=True,
                solo=False,
                inserts=[InsertPlugin(id="i1", plugin="compressor", preset="vocal")],
            )
        ],
    )
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored.follow_playback_enabled is True
    assert restored.realtime_meter_enabled is True
    assert restored.render_preview_enabled is True
    assert restored.auto_mix_enabled is True
    assert restored.auto_mix_style == "studio"
    assert restored.master_volume_db == -2.5
    assert restored.master_inserts[0].preset == "safe-2"
    assert restored.tracks[0].volume_db == -4.0
    assert restored.tracks[0].pan == 0.25
    assert restored.tracks[0].mute is True
    assert restored.tracks[0].inserts[0].preset == "vocal"
    assert restored.export_panel_visible is False
    assert restored.metadata_panel_visible is False
    assert restored.timeline_zoom_px_per_sec == 135
    assert restored.mixer_meta_tab == "markers"
    assert restored.export_format == "flac"


def test_frontend_saves_zoom_export_and_meta_tab_into_project():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert "current.timeline_zoom_px_per_sec=pxPerSec" in js
    assert "current.export_format=format" in js
    assert "current.mixer_meta_tab=kind" in js
    assert "pxPerSec=Number(current.timeline_zoom_px_per_sec||70)" in js
    assert "mixerMetaTab=current.mixer_meta_tab||'lyrics'" in js
    assert "exportFormat=current.export_format||'mta'" in js
