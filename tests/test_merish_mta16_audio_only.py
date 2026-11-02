import pytest
from defusedxml import ElementTree as ET

from app.merish_mta16 import build_minimal_syl, build_settings_xml, extract_consistent_user_id, validate_audio_only
from app.models import Chord, LyricLine, Marker, MtaSlotMapping, Project


def _project():
    return Project(id="test", title="Test & title", artist="Artist", target="MTA16", merish_user_id="123456")


def test_new_project_default_and_existing_explicit_identity_are_preserved():
    assert Project(id="new", title="New").merish_user_id == "068336"
    assert Project(id="old", title="Old", merish_user_id="654321").merish_user_id == "654321"
    assert Project(id="old-empty", title="Old", merish_user_id="").merish_user_id == ""


def test_generated_metadata_is_user_specific_and_not_a_template():
    project = _project()
    slots = [MtaSlotMapping(slot=1, name="Click & time", type="click", track_ids=["a"]),
             MtaSlotMapping(slot=2, name="Music", type="other", track_ids=["b"])]
    xml = build_settings_xml(project, slots, 10448)
    parsed = ET.fromstring(xml.rstrip(b"\0"))
    assert parsed.findtext("Identity/UserId") == "123456"
    assert parsed.findtext("General/DurataSec") == "10"
    assert parsed.findtext("General/PreCntUSec") == "0"
    assert parsed.findtext("TrkAudio/Track/Nome") == "Click & time"
    assert len(parsed.findall("TrkAudio/Track")) == 2
    syl = build_minimal_syl(project, 10448)
    assert syl.startswith(b"ID3\x03\x00\x00") and b"Test & title" in syl
    assert b"LYRICSBEGIN" not in syl


@pytest.mark.parametrize('target,count', [('MTA8', 8), ('MTA16', 9)])
@pytest.mark.parametrize('content', ['audio', 'lyrics_chords', 'markers', 'combined'])
def test_merish_precount_is_zero_with_or_without_annotations(target, count, content):
    project = _project()
    project.target = target
    project.merish_syl_key = bytes(range(256)).hex()
    if content in ('lyrics_chords', 'combined'):
        project.lyrics = [LyricLine(time_ms=1000, text='TEST')]
        project.chords = [Chord(time_ms=1000, chord='C')]
    if content in ('markers', 'combined'):
        project.markers = [Marker(time_ms=2000, label='INTRO')]
    slots = [MtaSlotMapping(slot=i, name=f'Track {i}', type='other', track_ids=[f't{i}'])
             for i in range(1, count + 1)]
    xml = ET.fromstring(build_settings_xml(project, slots, 12000).rstrip(b'\0'))
    assert xml.findtext('General/PreCntUSec') == '0'


def test_device_track_roles_use_observed_names():
    project = _project()
    slots = [MtaSlotMapping(slot=1, name="Melody", type="melody", track_ids=["a"]),
             MtaSlotMapping(slot=2, name="Winds", type="winds", track_ids=["b"])]
    xml = ET.fromstring(build_settings_xml(project, slots, 10000).rstrip(b"\0"))
    assert [t.findtext("Type") for t in xml.findall("TrkAudio/Track")] == ["MELODIA", "WINDS"]


def test_project_key_is_written_as_id3_text_without_guessing_xml_base_key():
    from app.mta_reverse import inspect_embedded_id3

    project = _project()
    project.key = "Dm"
    frames = inspect_embedded_id3(build_minimal_syl(project, 10000))["frames"]
    assert [item["text"] for item in frames if item["id"] == "TKEY"] == ["Dm"]
    slots = [MtaSlotMapping(slot=1, name="Music", type="other", track_ids=["t"])]
    xml = ET.fromstring(build_settings_xml(project, slots, 10000).rstrip(b"\0"))
    assert xml.findtext("General/BaseKey") == "26"
    project.key = ""
    assert all(item["id"] != "TKEY" for item in inspect_embedded_id3(build_minimal_syl(project, 10000))["frames"])


@pytest.mark.parametrize("kind", ["lyrics", "chords"])
def test_text_requires_imported_metadata(kind):
    project = _project()
    values = {"lyrics": LyricLine(time_ms=0, text="hello"), "chords": Chord(time_ms=0, chord="C"),
              "markers": Marker(time_ms=0, label="intro")}
    getattr(project, kind).append(values[kind])
    with pytest.raises(ValueError, match="importa i metadati"):
        validate_audio_only(project)


def test_marker_only_export_encodes_markers_without_lyrics_or_colors():
    from app.mta_reverse import _decode_miditk_observed, _raw_proprietary_section_body

    project = _project()
    project.merish_syl_key = bytes(range(256)).hex()
    project.markers = [Marker(time_ms=0, label="intro")]
    syl = build_minimal_syl(project, 10000)
    assert _raw_proprietary_section_body(syl, "LYRICS") is None
    assert _raw_proprietary_section_body(syl, "COLORS") is None
    decoded = _decode_miditk_observed(_raw_proprietary_section_body(syl, "MIDITK"), list(bytes(range(256))))
    assert decoded["validated"] and [(event["text"], event["time_ms"]) for event in decoded["markers"]] == [("intro", 0)]


@pytest.mark.parametrize("mode", ["zones", "adaptive"])
def test_marker_export_allows_nonfixed_tempo_with_absolute_times(mode):
    from app.mta_reverse import _decode_miditk_observed, _raw_proprietary_section_body

    project = _granular_project()
    project.markers = [Marker(time_ms=2000, label="INTRO")]
    project.metronome_mode = mode
    validate_audio_only(project)
    syl = build_minimal_syl(project, 12000)
    decoded = _decode_miditk_observed(_raw_proprietary_section_body(syl, "MIDITK"), list(bytes(range(256))))
    assert decoded["validated"] and [(e["text"], round(e["time_ms"])) for e in decoded["markers"]] == [("INTRO", 2000)]


def test_marker_export_requires_key_and_rejects_mixed_lyric_timings():
    project = _granular_project()
    project.markers = [Marker(time_ms=2000, label="INTRO")]
    project.merish_syl_key = ""
    with pytest.raises(ValueError, match="importa i metadati"):
        validate_audio_only(project)
    project.merish_syl_key = bytes(range(256)).hex()
    project.lyrics[0].words = []
    with pytest.raises(ValueError, match="tutte le righe"):
        build_minimal_syl(project, 12000)


def test_marker_export_accepts_whole_line_lyrics_without_colors():
    from app.mta_reverse import _decode_miditk_observed, _decode_variable_section_observed, _raw_proprietary_section_body

    project = _project()
    key = bytes(range(256))
    project.merish_syl_key = key.hex()
    project.lyrics = [LyricLine(time_ms=0, text="CIAO MTA"), LyricLine(time_ms=3000, text="PROVA TESTO"),
                      LyricLine(time_ms=6000, text="FINE TEST")]
    project.chords = [Chord(time_ms=0, chord="C"), Chord(time_ms=3000, chord="F"), Chord(time_ms=6000, chord="G")]
    project.markers = [Marker(time_ms=2000, label="INTRO"), Marker(time_ms=5000, label="STROFA"),
                       Marker(time_ms=8000, label="FINALE")]
    syl = build_minimal_syl(project, 10000)
    assert _raw_proprietary_section_body(syl, "COLORS") is None
    lyrics = _decode_variable_section_observed(_raw_proprietary_section_body(syl, "LYRICS"), list(key), section="LYRICS")
    midi = _decode_miditk_observed(_raw_proprietary_section_body(syl, "MIDITK"), list(key))
    assert lyrics["validated"] and [(x["time_ms"], x["text"]) for x in lyrics["records"]] == [(0, "CIAO MTA"), (3000, "PROVA TESTO")]
    assert midi["validated"] and [round(x["time_ms"]) for x in midi["markers"]] == [2000, 5000, 8000]
    slots = [MtaSlotMapping(slot=1, name="Tone", type="other", track_ids=["t"])]
    xml = ET.fromstring(build_settings_xml(project, slots, 10000).rstrip(b"\0"))
    assert xml.findtext("General/PreCntUSec") == "0"


def _granular_project(mode="word"):
    from app.models import LyricWord
    project = _project()
    project.merish_syl_key = bytes(range(256)).hex()
    project.merish_lyric_highlight = mode
    project.lyrics = [LyricLine(time_ms=t, text=text, words=[
        LyricWord(start_ms=t, end_ms=t + 1600, text=first),
        LyricWord(start_ms=t + 1600, end_ms=t + 3000, text=second),
    ]) for t, text, first, second in [(0, "CIAO MTA", "CIAO", "MTA"),
                                      (3000, "PROVA TESTO", "PROVA", "TESTO"),
                                      (6000, "FINE TEST", "FINE", "TEST")]]
    return project


@pytest.mark.parametrize("mode,expected", [("word", {0: 127, 800: 0, 1600: 4, 3000: 127, 9000: 9}),
                                         ("character", {0: 127, 800: 2, 1600: 4, 3000: 127, 9000: 9})])
def test_granular_colors_match_verified_word_and_character_patterns(mode, expected):
    from app.mta_reverse import _decode_colors_observed, _raw_proprietary_section_body

    syl = build_minimal_syl(_granular_project(mode), 12000)
    result = _decode_colors_observed(_raw_proprietary_section_body(syl, "COLORS"))
    assert result["validated"] and result["normal_event_count"] == 256
    actual = {x["time_ms"]: x["highlight_position"] for x in result["events"]}
    assert {t: actual[t] for t in expected} == expected


@pytest.mark.parametrize("mode", ["word", "character"])
@pytest.mark.parametrize("duration_ms", [12000, 70000, 256 * 60000 + 1000])
def test_granular_colors_terminate_at_audio_end_with_correct_minute(mode, duration_ms):
    from app.mta_reverse import _decode_colors_observed, _raw_proprietary_section_body

    body = _raw_proprietary_section_body(build_minimal_syl(_granular_project(mode), duration_ms), "COLORS")
    result = _decode_colors_observed(body)
    assert result["validated"]
    last_normal = result["events"][-1]
    expected_end = min(duration_ms - 1, 256 * 60000 - 1)
    assert last_normal["next_minute_block"] == expected_end // 60000
    index = result["normal_event_count"]
    cipher = bytes.fromhex(result["terminal_record_hex"])
    plain = bytes(value ^ ((index - 17 * j) % 256) ^ 10 for j, value in enumerate(cipher))
    centiseconds = plain[1] * 1000 + plain[2] * 100 + plain[4] * 10 + plain[5]
    assert last_normal["next_minute_block"] * 60000 + centiseconds * 10 == expected_end // 10 * 10
    assert plain[7:] == b"\x00\x00\x00=:0=:"


def test_character_highlighting_uses_syllable_timing():
    from app.models import LyricSyllable
    from app.mta_reverse import _decode_colors_observed, _raw_proprietary_section_body

    project = _granular_project("character")
    project.lyrics[0].words[0].syllables = [LyricSyllable(text="CI", start_ms=0, end_ms=400),
                                             LyricSyllable(text="AO", start_ms=400, end_ms=1600)]
    result = _decode_colors_observed(_raw_proprietary_section_body(build_minimal_syl(project, 12000), "COLORS"))
    actual = {x["time_ms"]: x["highlight_position"] for x in result["events"]}
    assert actual[400] == 2 and actual[800] == 2 and actual[1600] == 4


def test_colors_preserve_minutes_and_centisecond_boundaries():
    from app.mta_reverse import _decode_colors_observed, _raw_proprietary_section_body

    project = _granular_project()
    project.lyrics = project.lyrics[:2]
    project.lyrics[1].time_ms = 62000
    project.lyrics[1].words[0].start_ms, project.lyrics[1].words[0].end_ms = 62000, 63605
    project.lyrics[1].words[1].start_ms, project.lyrics[1].words[1].end_ms = 63609, 65000
    result = _decode_colors_observed(_raw_proprietary_section_body(build_minimal_syl(project, 70000), "COLORS"))
    assert result["validated"]
    actual = {x["time_ms"]: x["highlight_position"] for x in result["events"]}
    assert actual[62000] == 127 and actual[63600] == 5 and actual[65000] == 11


@pytest.mark.parametrize("case,match", [("mixed", "tutte le righe"), ("mismatch", "non corrispondenti"),
                                        ("overlap", "sovrapposti"), ("long", "99 caratteri"),
                                        ("syllables", "sillabe non corrispondenti"), ("short", "2,56"),
                                        ("missing", "parole sincronizzate mancanti"), ("fast", "tempi delle parole")])
def test_granular_export_rejects_invalid_timelines(case, match):
    from app.models import LyricSyllable

    project = _granular_project("character")
    if case == "mixed": project.lyrics[1].words = []
    if case == "mismatch": project.lyrics[0].words[0].text = "ALTRO"
    if case == "overlap": project.lyrics[0].words[1].start_ms = 800
    if case == "long": project.lyrics[0].text += "x" * 100
    if case == "syllables": project.lyrics[0].words[0].syllables = [LyricSyllable(text="X", start_ms=0, end_ms=100)]
    if case == "short": project.lyrics = project.lyrics[:1]
    if case == "missing": project.lyrics[0].text += " PERSO"
    if case == "fast": project.lyrics[0].words[0].end_ms = 9
    with pytest.raises(ValueError, match=match):
        build_minimal_syl(project, 2500 if case == "short" else 12000)


def test_generated_text_and_chords_have_correct_timing_order_and_final_event():
    from app.mta_reverse import _decode_variable_section_observed, _raw_proprietary_section_body

    project = _project()
    key = bytes(range(256))
    project.merish_syl_key = key.hex()
    project.lyrics = [LyricLine(time_ms=3000, text="SECONDA"), LyricLine(time_ms=0, text="PRIMA"),
                      LyricLine(time_ms=62000, text="FINE")]
    project.chords = [Chord(time_ms=0, chord="C"), Chord(time_ms=3000, chord="F"),
                      Chord(time_ms=62000, chord="G")]
    syl = build_minimal_syl(project, 70000)
    for name, expected, suffix in (("LYRICS", [(0, "PRIMA"), (3000, "SECONDA")], b"0=:0=:"),
                                    ("CHORDS", [(0, "C"), (3000, "F")], b"=:")):
        body = _raw_proprietary_section_body(syl, name)
        result = _decode_variable_section_observed(body, list(key), section=name)
        assert result["validated"]
        assert [(record["time_ms"], record["text"]) for record in result["records"]] == expected
        plaintext = bytes(value ^ key[(239 * i) % 256] ^ 10 for i, value in enumerate(body[3:]))
        assert plaintext.endswith(suffix)


@pytest.mark.parametrize("text,time,duration,match", [
    ("test", 60000, 120000, "primo minuto"),
    ("test", 1000, 1000, "fine del brano"),
    ("x" * 127, 0, 1000, "126 caratteri"),
    ("test\ninvalid", 0, 1000, "controllo"),
    ("東京", 0, 1000, "Latin-1"),
])
def test_text_format_limits_are_explicit(text, time, duration, match):
    project = _project()
    project.merish_syl_key = bytes(range(256)).hex()
    project.lyrics = [LyricLine(time_ms=time, text=text)]
    with pytest.raises(ValueError, match=match):
        build_minimal_syl(project, duration)


def test_user_id_validation_and_import_conflict():
    project = _project()
    project.merish_user_id = "000000"
    with pytest.raises(ValueError, match="identificativo"):
        validate_audio_only(project)
    def xml(identity):
        return f'<?xml version="1.0"?><MtxInfoData><Identity><UserId>{identity}</UserId></Identity></MtxInfoData>'.encode()
    assert extract_consistent_user_id([xml("123456"), xml("123456") + bytes(100)]) == "123456"
    assert extract_consistent_user_id([xml("123456"), xml("654321")]) is None
    assert extract_consistent_user_id([xml("000000")]) is None
    assert extract_consistent_user_id([b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "x">]><a>&x;</a>']) is None


@pytest.mark.skipif(__import__("shutil").which("ffmpeg") is None, reason="FFmpeg required")
def test_project_export_embeds_four_ordered_audio_only_attachments(tmp_path, monkeypatch):
    import json
    import subprocess

    from app import storage
    from app.codec import export_mta
    from app.models import Clip, Track
    from app.mta_reverse import _scan_matroska_filedata, deobfuscate_media_copy

    monkeypatch.setattr(storage, "ROOT", (tmp_path / "projects").resolve())
    project = storage.create_project("Export Test", target="MTA16")
    project.merish_user_id = "123456"
    source = storage.audio_path(project.id, "tone.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1", str(source)], check=True)
    project.tracks = [Track(id="track1", name="Tone", type="other", filename=source.name,
                            duration_ms=1000, clips=[Clip(id="clip1", source_end_ms=1000)])]
    output = tmp_path / "audio.mta"
    export_mta(project, output, profile="merish5_plus_mta16")
    canonical = tmp_path / "audio.mka"
    deobfuscate_media_copy(output, canonical)
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(canonical)]))
    attachments = [s for s in info["streams"] if s.get("codec_type") == "attachment"]
    assert [s["tags"]["title"] for s in attachments[:4]] == [
        "ORG: ID3 LYRICS COLORS MIDITK(+MARKER) CHORDS", "MOD: ID3 LYRICS COLORS MIDITK(+MARKER) CHORDS",
        "ORG: MTX SETTINGS", "MOD: MTX SETTINGS"]
    assert [s["tags"]["filename"] for s in attachments[:4]] == ["project.syl", "project.syl", "project.xml", "project.xml"]
    sizes = [s["extradata_size"] for s in attachments]
    payloads = _scan_matroska_filedata(canonical, sizes)
    assert payloads[0] == payloads[1] and payloads[0].startswith(b"ID3")
    assert payloads[2] == payloads[3] and b"<UserId>123456</UserId>" in payloads[2]


@pytest.mark.skipif(__import__("shutil").which("ffmpeg") is None, reason="FFmpeg required")
def test_experimental_mta8_exports_eight_slots_in_xynthia_order(tmp_path, monkeypatch):
    import json
    import subprocess

    from app import storage
    from app.codec import export_mta
    from app.models import Clip, Track
    from app.mta_reverse import _scan_matroska_filedata, deobfuscate_media_copy

    monkeypatch.setattr(storage, "ROOT", (tmp_path / "projects").resolve())
    project = storage.create_project("MTA8 test", target="MTA8")
    project.merish_user_id = "123456"
    source = storage.audio_path(project.id, "tone.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1", str(source)], check=True)
    project.tracks = [Track(id="click", name="Click", type="click", filename=source.name,
                            duration_ms=1000, clips=[Clip(id="clip1", source_end_ms=1000)]),
                      Track(id="melody", name="Melody", type="melody", filename=source.name,
                            duration_ms=1000, clips=[Clip(id="clip2", source_end_ms=1000)])]
    output = tmp_path / "audio.mta"
    export_mta(project, output, profile="merish5_xynthia2_experimental")
    canonical = tmp_path / "audio.mka"
    deobfuscate_media_copy(output, canonical)
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(canonical)]))
    audio = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    assert len(audio) == 8
    assert audio[6]["tags"]["MTA_TYPE"] == "melody" and audio[7]["tags"]["MTA_TYPE"] == "click"
    attachments = [s for s in info["streams"] if s.get("codec_type") == "attachment"]
    payloads = _scan_matroska_filedata(canonical, [s["extradata_size"] for s in attachments])
    xml = ET.fromstring(payloads[2].rstrip(b"\0"))
    assert [t.findtext("Type") for t in xml.findall("TrkAudio/Track")] == [
        "DRUM", "BASS", "GUITAR", "KEYBOARD", "ORCHESTRA", "WINDS", "MELODIA", "CLICK"]
    assert len(attachments) == 5 and payloads[0] == payloads[1] and payloads[2] == payloads[3]


def test_mta8_experimental_rejects_incorrect_click_slot(tmp_path, monkeypatch):
    from app import storage
    from app.codec import export_mta
    from app.models import Clip, Track

    monkeypatch.setattr(storage, "ROOT", (tmp_path / "projects").resolve())
    project = storage.create_project("MTA8 test", target="MTA8")
    project.merish_user_id = "123456"
    project.tracks = [Track(id="click", name="Click", type="click", filename="unused.wav",
                            clips=[Clip(id="clip1", source_end_ms=1000)])]
    wrong = [MtaSlotMapping(slot=1, name="Click", type="click", track_ids=["click"])]
    with pytest.raises(ValueError, match="slot 8"):
        export_mta(project, tmp_path / "output.mta", wrong, profile="merish5_xynthia2_experimental")


def _synthetic_syl_with_colors(key):
    from app.merish_mta16 import _event_stamp, _synchsafe

    records = []
    for i in range(257):
        plain = _event_stamp(i * 40) + b'\x00\x00\x00'
        plain += b'=:k\x00\x00' if i < 256 else b'=:0=:'
        records.append(bytes(value ^ key[(i - 17 * j) % 256] ^ 10 for j, value in enumerate(plain)))
    body = b'\x28\xb6\xa9' + b''.join(records)
    header = f'COLORSBEGININD0000211LYR{len(body):05d}\r\n'.encode()
    footer = f'{len(header)-2+len(body):06d}COLORS200\r\n'.encode()
    payload = header + body + footer
    return b'ID3\x03\x00\x00' + _synchsafe(len(payload)) + payload


def test_extract_syl_key_requires_consistent_valid_synthetic_records():
    from app.merish_mta16 import extract_consistent_syl_key

    key = bytes(range(256))
    first = _synthetic_syl_with_colors(key)
    other = _synthetic_syl_with_colors(bytes(reversed(key)))
    assert extract_consistent_syl_key([first, first]) == key.hex()
    assert extract_consistent_syl_key([first, other]) is None
    assert extract_consistent_syl_key([b'ID3bad']) is None


@pytest.mark.skipif(__import__('shutil').which('ffmpeg') is None, reason='FFmpeg required')
def test_import_merish_metadata_from_uploaded_file_and_reject_conflict(tmp_path, monkeypatch):
    import asyncio
    import subprocess

    from fastapi import HTTPException, UploadFile
    from app import main

    key = bytes(range(256))
    syl = tmp_path / 'source.syl'
    syl.write_bytes(_synthetic_syl_with_colors(key))
    xml = tmp_path / 'source.xml'
    xml.write_bytes(b'<?xml version="1.0"?><MtxInfoData><Identity><UserId>123456</UserId></Identity></MtxInfoData>')
    source = tmp_path / 'source.mta'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=duration=0.1',
                    '-attach', str(syl), '-metadata:s:t:0', 'mimetype=application/octet-stream',
                    '-attach', str(xml), '-metadata:s:t:1', 'mimetype=application/xml',
                    '-f', 'matroska', str(source)], check=True)
    project = Project(id="test", title="Test", target="MTA16")
    saved = []
    def authorize(request, pid, *, owner_only=False):
        assert owner_only and pid == project.id
        return project
    monkeypatch.setattr(main, '_project_for_actor', authorize)
    monkeypatch.setattr(main, 'save_project', lambda value: saved.append(value.model_copy(deep=True)))
    with source.open('rb') as file:
        result = asyncio.run(main.import_merish_metadata(project.id, None, UploadFile(filename='test.mta', file=file)))
    assert result['ok'] and saved[0].merish_user_id == '123456' and saved[0].merish_syl_key == key.hex()
    project.merish_user_id = '654321'
    with source.open('rb') as file, pytest.raises(HTTPException) as exc:
        asyncio.run(main.import_merish_metadata(project.id, None, UploadFile(filename='test.mta', file=file)))
    assert exc.value.status_code == 409 and len(saved) == 1
    project.merish_user_id = '068336'
    with source.open('rb') as file, pytest.raises(HTTPException) as exc:
        asyncio.run(main.import_merish_metadata(project.id, None, UploadFile(filename='test.mta', file=file)))
    assert exc.value.status_code == 409 and len(saved) == 1


@pytest.mark.parametrize('target,profile,mode', [
    ('MTA8', 'merish5_xynthia2_experimental', 'word'),
    ('MTA8', 'merish5_xynthia2_experimental', 'character'),
    ('MTA16', 'merish5_plus_mta16', 'word'),
    ('MTA16', 'merish5_plus_mta16', 'character'),
])
@pytest.mark.skipif(__import__('shutil').which('ffmpeg') is None, reason='FFmpeg required')
def test_export_generates_granular_syl_and_preserves_mode(tmp_path, monkeypatch, target, profile, mode):
    import json
    import subprocess

    from app import storage
    from app.codec import export_mta
    from app.models import Clip, LyricWord, Track
    from app.mta_reverse import _decode_colors_observed, _decode_miditk_observed, _raw_proprietary_section_body, _scan_matroska_filedata, deobfuscate_media_copy, inspect_embedded_id3

    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Granular test', target=target)
    project.merish_syl_key = bytes(range(256)).hex()
    project.merish_lyric_highlight = mode
    project.key = 'Dm'
    project.markers = [Marker(time_ms=2000, label='INTRO')]
    project.lyrics = [LyricLine(time_ms=0, text='CIAO MTA', words=[
        LyricWord(start_ms=0, end_ms=1600, text='CIAO'), LyricWord(start_ms=1600, end_ms=3000, text='MTA')])]
    source = storage.audio_path(project.id, 'tone.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=duration=4', str(source)], check=True)
    project.tracks = [Track(id='t', name='Tone', type='other', filename=source.name, duration_ms=4000,
                            clips=[Clip(id='c', source_end_ms=4000)])]
    output = tmp_path / 'output.mta'
    export_mta(project, output, profile=profile)
    canonical = tmp_path / 'output.mka'
    deobfuscate_media_copy(output, canonical)
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(canonical)]))
    attachments = [s for s in info['streams'] if s.get('codec_type') == 'attachment']
    names = [(s.get('tags') or {}).get('filename') for s in attachments]
    payloads = _scan_matroska_filedata(canonical, [s['extradata_size'] for s in attachments])
    syl = payloads[names.index('project.syl')]
    assert [frame['text'] for frame in inspect_embedded_id3(syl)['frames'] if frame['id'] == 'TKEY'] == ['Dm']
    colors = _decode_colors_observed(_raw_proprietary_section_body(syl, 'COLORS'))
    assert colors['validated'] and colors['normal_event_count'] >= 256
    actual = {item['time_ms']: item['highlight_position'] for item in colors['events']}
    assert actual[800] == (0 if mode == 'word' else 2)
    marker_data = _decode_miditk_observed(_raw_proprietary_section_body(syl, 'MIDITK'), list(bytes(range(256))))
    assert marker_data['validated'] and [(x['text'], round(x['time_ms'])) for x in marker_data['markers']] == [('INTRO', 2000)]
    xml = ET.fromstring(payloads[names.index('project.xml')].rstrip(b'\0'))
    assert xml.findtext('General/PreCntUSec') == '0'
    synced = json.loads(payloads[names.index('mta-synchronized-text.json')])
    assert synced['merish_lyric_highlight'] == mode
    assert [word['text'] for word in synced['lyrics'][0]['words']] == ['CIAO', 'MTA']
    if target == 'MTA8' and mode == 'character':
        from app.codec import import_mta

        restored = storage.create_project('Restored granular', target=target)
        import_mta(output, restored)
        assert restored.merish_lyric_highlight == 'character'
        assert [word.text for word in restored.lyrics[0].words] == ['CIAO', 'MTA']
        assert [(marker.time_ms, marker.label) for marker in restored.markers] == [(2000, 'INTRO')]


def test_experimental_marker_probe_roundtrips_midi_without_audio_notes():
    from app.merish_mta16 import _experimental_marker_miditk
    from app.mta_reverse import _decode_miditk_observed, _raw_proprietary_section_body

    project = _project()
    project.bpm = 117
    project.markers = [Marker(time_ms=5000, label='STROFA'), Marker(time_ms=2000, label='INTRO'),
                       Marker(time_ms=8000, label='FINALE'), Marker(time_ms=1000, label='Hidden', disabled=True)]
    key = bytes(range(256))
    section = _experimental_marker_miditk(project, 12000, key)
    body = _raw_proprietary_section_body(section, 'MIDITK')
    parsed = _decode_miditk_observed(body, list(key))
    assert parsed['validated'] and parsed['format'] == 0 and parsed['ppq'] == 480
    assert [item['text'] for item in parsed['markers']] == ['INTRO', 'STROFA', 'FINALE']
    assert all(abs(event['time_ms'] - expected) < 2 for event, expected in zip(parsed['markers'], [2000, 5000, 8000]))
    assert {event['kind'] for event in parsed['meta_events']} == {'tempo', 'marker', 'end_of_track'}
    project.merish_syl_key = key.hex()
    validate_audio_only(project)


@pytest.mark.parametrize('label,time,duration,match', [
    ('OK', 12000, 12000, 'fine del brano'),
    ('', 100, 12000, 'nome marker'),
    ('BAD\nTEXT', 100, 12000, 'controllo'),
    ('東京', 100, 12000, 'Latin-1'),
])
def test_experimental_marker_probe_rejects_invalid_events(label, time, duration, match):
    from app.merish_mta16 import _experimental_marker_miditk

    project = _project()
    project.markers = [Marker(time_ms=time, label=label)]
    with pytest.raises(ValueError, match=match):
        _experimental_marker_miditk(project, duration, bytes(range(256)))


@pytest.mark.parametrize('target,profile', [('MTA8', 'merish5_xynthia2_experimental'), ('MTA16', 'merish5_plus_mta16')])
@pytest.mark.skipif(__import__('shutil').which('ffmpeg') is None, reason='FFmpeg required')
def test_export_marker_only_without_lyrics_keeps_timing_and_no_colors(tmp_path, monkeypatch, target, profile):
    import json
    import subprocess

    from app import storage
    from app.codec import export_mta
    from app.models import Clip, Track
    from app.mta_reverse import _decode_miditk_observed, _raw_proprietary_section_body, _scan_matroska_filedata, deobfuscate_media_copy

    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Marker only', target=target)
    project.merish_syl_key = bytes(range(256)).hex()
    project.markers = [Marker(time_ms=2000, label='INTRO'), Marker(time_ms=3000, label='STROFA')]
    source = storage.audio_path(project.id, 'tone.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=duration=4', str(source)], check=True)
    project.tracks = [Track(id='t', name='Tone', type='other', filename=source.name, duration_ms=4000,
                            clips=[Clip(id='c', source_end_ms=4000)])]
    output = tmp_path / 'output.mta'
    export_mta(project, output, profile=profile)
    canonical = tmp_path / 'output.mka'
    deobfuscate_media_copy(output, canonical)
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(canonical)]))
    attachments = [s for s in info['streams'] if s.get('codec_type') == 'attachment']
    names = [(s.get('tags') or {}).get('filename') for s in attachments]
    payloads = _scan_matroska_filedata(canonical, [s['extradata_size'] for s in attachments])
    syl = payloads[names.index('project.syl')]
    assert _raw_proprietary_section_body(syl, 'LYRICS') is None
    assert _raw_proprietary_section_body(syl, 'COLORS') is None
    marker_data = _decode_miditk_observed(_raw_proprietary_section_body(syl, 'MIDITK'), list(bytes(range(256))))
    assert marker_data['validated']
    assert [(x['text'], round(x['time_ms'])) for x in marker_data['markers']] == [('INTRO', 2000), ('STROFA', 3000)]
    xml = ET.fromstring(payloads[names.index('project.xml')].rstrip(b'\0'))
    assert xml.findtext('General/PreCntUSec') == '0'
    synced = json.loads(payloads[names.index('mta-synchronized-text.json')])
    assert [(x['label'], x['time_ms']) for x in synced['markers']] == [('INTRO', 2000), ('STROFA', 3000)]


def _variable_marker_project(mode):
    from app.models import AdaptiveTempoPoint

    project = _project()
    project.metronome_mode = mode
    project.bpm = project.base_bpm = 120
    project.markers = [Marker(id='intro', time_ms=2000, label='INTRO'),
                       Marker(id='verse', time_ms=5000, label='STROFA'),
                       Marker(id='end', time_ms=8000, label='FINALE')]
    if mode == 'adaptive':
        project.adaptive_tempo_map = [AdaptiveTempoPoint(time_ms=0, bpm=120, beat_index=0),
                                      AdaptiveTempoPoint(time_ms=4000, bpm=90, beat_index=8),
                                      AdaptiveTempoPoint(time_ms=8000, bpm=150, beat_index=14),
                                      AdaptiveTempoPoint(time_ms=10000, bpm=150, beat_index=19)]
    else:
        project.metronome_zone_bpms = {'0': 120, '2000': 90, '5000': 150, '8000': 120}
    return project


@pytest.mark.parametrize('mode', ['zones', 'adaptive'])
@pytest.mark.parametrize('signature', ['4/4', '6/8'])
def test_variable_tempo_marker_probe_keeps_absolute_marker_times(mode, signature):
    from app.merish_mta16 import _experimental_variable_marker_miditk
    from app.mta_reverse import _decode_miditk_observed, _raw_proprietary_section_body

    project = _variable_marker_project(mode)
    project.time_signature = signature
    key = bytes(range(256))
    section = _experimental_variable_marker_miditk(project, 10000, key)
    midi = _decode_miditk_observed(_raw_proprietary_section_body(section, 'MIDITK'), list(key))
    assert midi['validated'] and len(midi['tempo_events']) >= 3
    assert [event['text'] for event in midi['markers']] == ['INTRO', 'STROFA', 'FINALE']
    assert all(abs(event['time_ms'] - expected) < 5 for event, expected in zip(midi['markers'], [2000, 5000, 8000]))
    project.merish_syl_key = key.hex()
    validate_audio_only(project)


def test_variable_tempo_marker_probe_rejects_missing_map():
    from app.merish_mta16 import _experimental_variable_marker_miditk

    project = _variable_marker_project('adaptive')
    project.adaptive_tempo_map = []
    with pytest.raises(ValueError, match='mappa di tempo adattiva mancante'):
        _experimental_variable_marker_miditk(project, 10000, bytes(range(256)))


@pytest.mark.parametrize('target,profile', [('MTA8', 'merish5_xynthia2_experimental'), ('MTA16', 'merish5_plus_mta16')])
@pytest.mark.skipif(__import__('shutil').which('ffmpeg') is None, reason='FFmpeg required')
def test_export_markers_with_line_lyrics_without_colors(tmp_path, monkeypatch, target, profile):
    import json
    import subprocess

    from app import storage
    from app.codec import export_mta
    from app.models import Clip, Track
    from app.mta_reverse import _decode_miditk_observed, _raw_proprietary_section_body, _scan_matroska_filedata, deobfuscate_media_copy

    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Line marker', target=target)
    project.merish_syl_key = bytes(range(256)).hex()
    project.lyrics = [LyricLine(time_ms=0, text='CIAO'), LyricLine(time_ms=1500, text='FINE')]
    project.markers = [Marker(time_ms=2000, label='INTRO')]
    source = storage.audio_path(project.id, 'tone.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=duration=4', str(source)], check=True)
    project.tracks = [Track(id='t', name='Tone', type='other', filename=source.name, duration_ms=4000,
                            clips=[Clip(id='c', source_end_ms=4000)])]
    output = tmp_path / 'output.mta'
    export_mta(project, output, profile=profile)
    canonical = tmp_path / 'output.mka'
    deobfuscate_media_copy(output, canonical)
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(canonical)]))
    attachments = [s for s in info['streams'] if s.get('codec_type') == 'attachment']
    names = [(s.get('tags') or {}).get('filename') for s in attachments]
    payloads = _scan_matroska_filedata(canonical, [s['extradata_size'] for s in attachments])
    syl = payloads[names.index('project.syl')]
    assert _raw_proprietary_section_body(syl, 'LYRICS') is not None
    assert _raw_proprietary_section_body(syl, 'COLORS') is None
    midi = _decode_miditk_observed(_raw_proprietary_section_body(syl, 'MIDITK'), list(bytes(range(256))))
    assert midi['validated'] and [(x['text'], round(x['time_ms'])) for x in midi['markers']] == [('INTRO', 2000)]
    assert ET.fromstring(payloads[names.index('project.xml')].rstrip(b'\0')).findtext('General/PreCntUSec') == '0'


@pytest.mark.parametrize('target,profile', [('MTA8', 'merish5_xynthia2_experimental'), ('MTA16', 'merish5_plus_mta16')])
@pytest.mark.parametrize('mode', ['zones', 'adaptive'])
@pytest.mark.skipif(__import__('shutil').which('ffmpeg') is None, reason='FFmpeg required')
def test_variable_metronome_audio_and_markers_export_to_merish(tmp_path, monkeypatch, target, profile, mode):
    import json
    import subprocess

    import numpy as np
    import soundfile as sf

    from app import storage
    from app.codec import export_mta
    from app.models import AdaptiveTempoPoint, Clip, Track
    from app.mta_reverse import _decode_miditk_observed, _raw_proprietary_section_body, _scan_matroska_filedata, deobfuscate_media_copy

    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Variable tempo audio', target=target)
    project.merish_syl_key = bytes(range(256)).hex()
    project.metronome_mode = mode
    project.markers = [Marker(id='m1', time_ms=2000, label='STROFA'), Marker(id='m2', time_ms=3000, label='FINALE')]
    project.metronome_zone_bpms = {'0': 120, '2000': 90}
    if mode == 'adaptive':
        project.adaptive_tempo_map = [AdaptiveTempoPoint(time_ms=0, bpm=120, beat_index=0),
                                      AdaptiveTempoPoint(time_ms=2000, bpm=90, beat_index=4),
                                      AdaptiveTempoPoint(time_ms=4000, bpm=90, beat_index=7)]
    rate = 44100
    beats = [0.25, 0.75, 1.25, 1.75, 2.25, 2.9167, 3.5833]
    data = np.zeros(rate * 4, dtype=np.float32)
    t = np.arange(round(rate * .08)) / rate
    click = (.7 * np.sin(2 * np.pi * 880 * t) * np.hanning(len(t))).astype(np.float32)
    for time in beats:
        start = round(time * rate)
        data[start:start + len(click)] = click
    source = storage.audio_path(project.id, 'click.wav')
    sf.write(source, data, rate, subtype='PCM_16')
    project.tracks = [Track(id='click', name='Click', type='click', filename=source.name, duration_ms=4000,
                            clips=[Clip(id='clip', source_end_ms=4000)])]
    output = tmp_path / 'output.mta'
    export_mta(project, output, profile=profile)
    assert project.metronome_mode == mode and project.metronome_zone_bpms == {'0': 120, '2000': 90}
    if mode == 'adaptive':
        assert [(point.time_ms, point.beat_index) for point in project.adaptive_tempo_map] == [(0, 0), (2000, 4), (4000, 7)]
    canonical = tmp_path / 'output.mka'
    deobfuscate_media_copy(output, canonical)
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(canonical)]))
    audio = [stream for stream in info['streams'] if stream.get('codec_type') == 'audio']
    click_index = next(i for i, stream in enumerate(audio) if (stream.get('tags') or {}).get('MTA_TYPE') == 'click')
    assert click_index == (7 if target == 'MTA8' else 0)
    decoded = np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(canonical), '-map', f'0:a:{click_index}',
                                                     '-ac', '1', '-ar', '8000', '-f', 'f32le', '-']), dtype='<f4')
    for beat in beats:
        window = decoded[max(0, round((beat - .03) * 8000)):round((beat + .14) * 8000)]
        assert len(window) and np.max(abs(window)) > .03, (mode, target, beat)
    attachments = [stream for stream in info['streams'] if stream.get('codec_type') == 'attachment']
    names = [(stream.get('tags') or {}).get('filename') for stream in attachments]
    payloads = _scan_matroska_filedata(canonical, [stream['extradata_size'] for stream in attachments])
    syl = payloads[names.index('project.syl')]
    midi = _decode_miditk_observed(_raw_proprietary_section_body(syl, 'MIDITK'), list(bytes(range(256))))
    assert midi['validated'] and [(event['text'], round(event['time_ms'])) for event in midi['markers']] == [('STROFA', 2000), ('FINALE', 3000)]
    assert len(midi['tempo_events']) == 1 and midi['tempo_events'][0]['bpm'] == 120
    xml = ET.fromstring(payloads[names.index('project.xml')].rstrip(b'\0'))
    assert xml.findtext('General/BaseBpm') == '120' and xml.findtext('General/PreCntUSec') == '0'
