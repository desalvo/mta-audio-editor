from pathlib import Path

from app.models import Project, Track
from app.codec import suggested_slots
from app.plugins import FACTORY_PARAMS, PRESETS, validate_custom_params

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
USER_IT = (ROOT / "app/docs/user.html").read_text(encoding="utf-8")
USER_EN = (ROOT / "app/docs/user-en.html").read_text(encoding="utf-8")


def mk_track(track_id: str, name: str, slot=None, typ="other") -> Track:
    return Track(id=track_id, name=name, type=typ, mta_slot=slot, filename=f"{track_id}.wav")


def test_track_slot_persists_and_drives_suggested_mapping():
    project = Project(id="p1", title="demo", target="MTA8", tracks=[
        mk_track("a", "A", 5),
        mk_track("b", "B", 2),
        mk_track("c", "C", None),
    ])
    slots = suggested_slots(project, "generic")
    by_track = {tid: item["slot"] for item in slots for tid in item["track_ids"]}
    assert by_track["a"] == 5
    assert by_track["b"] == 2
    assert by_track["c"] == 1


def test_every_factory_preset_has_schema_valid_visible_params():
    for plugin, presets in PRESETS.items():
        assert plugin in FACTORY_PARAMS
        assert set(FACTORY_PARAMS[plugin]) == set(presets)
        for preset, params in FACTORY_PARAMS[plugin].items():
            validated = validate_custom_params(plugin, params)
            assert set(validated) == set(params)


def test_ui_exposes_slot_and_synced_rotary_controls():
    assert "MTA Slot" in JS
    assert "setTrackMtaSlot" in JS
    assert "factory_params" in JS
    assert "presetParamsFor" in JS
    assert "syncPluginControl" in JS
    assert "plugin-knob-shell" in CSS
    assert "plugin-number" in CSS


def test_user_manual_defines_mta_and_online_auth_scope():
    assert "MTA</b> significa <b>Multi Track Audio" in USER_IT
    assert "MTA</b> means <b>Multi Track Audio" in USER_EN
    assert "Utenti, password, TOTP" in USER_IT
    assert "Users, passwords, TOTP" in USER_EN
    assert "MTA Slot" in USER_IT and "MTA Slot" in USER_EN
    assert "plugin-editor.png" in USER_IT and "plugin-editor.png" in USER_EN


def test_readme_links_directly_to_both_pdf_languages():
    for path in [
        "app/docs/MTA-Audio-Editor-User-Manual-IT.pdf",
        "app/docs/MTA-Audio-Editor-User-Manual-EN.pdf",
        "app/docs/MTA-Audio-Editor-Administrator-Manual-IT.pdf",
        "app/docs/MTA-Audio-Editor-Administrator-Manual-EN.pdf",
    ]:
        assert path in README
