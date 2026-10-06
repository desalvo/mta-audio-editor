from pathlib import Path

from app.main import _audible_export_project, _musical_export_project
from app.models import Project, Track


ROOT = Path(__file__).resolve().parents[1]


def _track(track_id: str, *, mute: bool = False, height_px: int = 78) -> Track:
    return Track(
        id=track_id,
        name=track_id,
        filename=f"{track_id}.wav",
        duration_ms=1000,
        mute=mute,
        height_px=height_px,
    )


def test_export_view_omits_muted_tracks():
    project = Project(id="p", title="Song", tracks=[_track("audible"), _track("muted", mute=True)])
    exported = _audible_export_project(project)
    assert [track.id for track in exported.tracks] == ["audible"]
    assert [track.id for track in project.tracks] == ["audible", "muted"]


def test_mta_export_view_also_omits_muted_tracks():
    project = Project(id="p", title="Song", tracks=[_track("audible"), _track("muted", mute=True)])
    exported = _musical_export_project(project)
    assert [track.id for track in exported.tracks] == ["audible"]


def test_track_height_is_persistent_and_bounded():
    track = _track("t", height_px=160)
    restored = Track.model_validate(track.model_dump())
    assert restored.height_px == 160
    assert _track("default").height_px == 78


def test_native_sidebar_uses_manual_save_and_hides_redundant_local_save():
    html = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert 'id="saveProjectManualNav"' in html
    assert 'onclick="save()"' in html
    assert 'id="saveProjectLocalNav"' in html
    assert "if(manualSave)manualSave.hidden=false" in js
    assert "if(localSave)localSave.hidden=true" in js


def test_tracks_view_exposes_per_track_vertical_resize():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert "function beginTrackHeightResize(" in js
    assert "height_px" in js
    assert "track-height-resizer" in css
