from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models import Clip, MtaSlotMapping, Project, Track
from app.mta_reverse import analyze_blob, diff_blobs

WRITE_HEADERS = {"X-MTA-Request": "1"}


def _track(i: int) -> Track:
    return Track(id=f"t{i}", name=f"Track {i}", type="other", filename=f"t{i}.wav", duration_ms=1000,
                 clips=[Clip(id=f"c{i}", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)])


def test_project_can_exceed_mta_mix_capacity(tmp_path, monkeypatch):
    import app.storage as storage
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    p = storage.create_project("Large mix", "MTA8")
    for i in range(10):
        (storage.pdir(p.id) / "audio" / f"t{i}.wav").write_bytes(b"x")
        p.tracks.append(_track(i))
    storage.save_project(p)
    storage.validate_project_files(p)  # editing/mixing capacity is intentionally independent from MTA slot capacity


def test_mta_mapping_requires_every_track_once():
    import app.codec as codec
    p = Project(id="p", title="P", target="MTA8", tracks=[_track(i) for i in range(9)])
    with pytest.raises(ValueError):
        codec.validate_slot_mapping(p, None)
    slots = [MtaSlotMapping(slot=i + 1, name=f"S{i+1}", type="other", track_ids=[f"t{i}"]) for i in range(7)]
    slots.append(MtaSlotMapping(slot=8, name="Merged", type="other", track_ids=["t7", "t8"]))
    assert len(codec.validate_slot_mapping(p, slots)) == 8


def test_single_track_export_and_flac_master_routes(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    p = storage.create_project("Export formats")
    (storage.pdir(p.id) / "audio" / "t0.wav").write_bytes(b"x")
    p.tracks = [_track(0)]
    storage.save_project(p)
    monkeypatch.setattr(main, "render_track_export", lambda track, source, out, fmt="wav", **kwargs: Path(out).write_bytes(b"track") or out)
    monkeypatch.setattr(main, "render_mix", lambda project, resolver, out, fmt="mp3", bitrate="320k": Path(out).write_bytes(b"mix") or out)
    c = TestClient(main.app, headers=WRITE_HEADERS)
    assert c.get(f"/api/projects/{p.id}/tracks/t0/export?format=wav").status_code == 200
    assert c.get(f"/api/projects/{p.id}/tracks/t0/export?format=mp3").status_code == 200
    assert c.get(f"/api/projects/{p.id}/tracks/t0/export?format=flac").status_code == 200
    assert c.get(f"/api/projects/{p.id}/export?format=flac").status_code == 200


def test_export_plan_reports_over_capacity(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    p = storage.create_project("Map", "MTA8")
    for i in range(9):
        (storage.pdir(p.id) / "audio" / f"t{i}.wav").write_bytes(b"x")
        p.tracks.append(_track(i))
    storage.save_project(p)
    c = TestClient(main.app, headers=WRITE_HEADERS)
    data = c.get(f"/api/projects/{p.id}/export-plan").json()
    assert data["requires_mapping"] is True
    assert data["max_output_slots"] == 8


def test_reverse_blob_analysis_and_binary_diff():
    blob = b"SYL\x00hello world\x00" + (1000).to_bytes(4, "little") + b"lyrics text"
    report = analyze_blob(blob, "song.syl")
    assert report["looks_like_syl"] is True
    assert report["sha256"]
    diff = diff_blobs(b"abcdef", b"abcXefg")
    assert diff["common_prefix_bytes"] == 3
    assert diff["changed_ranges"]


def test_embedded_id3_inspection_sections():
    from app.mta_reverse import inspect_embedded_id3
    payload = b"LYRICS\x00CHORDS\x00MARKER\x00COLORS"
    frame = b"TXXX" + len(payload).to_bytes(4, "big") + b"\x00\x00" + payload
    size = len(frame)
    syn = bytes([(size >> 21) & 0x7f, (size >> 14) & 0x7f, (size >> 7) & 0x7f, size & 0x7f])
    blob = b"prefix" + b"ID3\x03\x00\x00" + syn + frame
    info = inspect_embedded_id3(blob)
    assert info["version"] == "2.3.0"
    assert info["frames"][0]["id"] == "TXXX"
    assert {"LYRICS", "CHORDS", "MARKER", "COLORS"} <= set(info["proprietary_section_labels"])


def test_extract_attachments_and_analyze_mta(tmp_path, monkeypatch):
    import app.mta_reverse as rev
    src = tmp_path / "demo.mta"; src.write_bytes(b"matroska-ish")
    info = {
        "streams": [
            {"index": 0, "codec_type": "audio", "codec_name": "mp3", "sample_rate": "44100", "channels": 2, "tags": {"title": "Drums"}},
            {"index": 1, "codec_type": "attachment", "tags": {"filename": "song.SYL"}},
        ],
        "format": {"format_name": "matroska,webm", "tags": {"TITLE": "Demo"}},
    }
    monkeypatch.setattr(rev, "probe", lambda path: info)
    def fake_run(cmd):
        for i, item in enumerate(cmd):
            if str(item).startswith("-dump_attachment:t:"):
                Path(cmd[i + 1]).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00LYRICS")
        return ""
    monkeypatch.setattr(rev, "_run", fake_run)
    outdir = tmp_path / "attachments"
    atts = rev.extract_attachments(src, outdir)
    assert atts[0]["looks_like_syl"] is True
    report = rev.analyze_mta(src, outdir)
    assert report["observations"]["container_is_matroska"] is True
    assert report["audio_streams"][0]["codec_name"] == "mp3"
    assert report["observations"]["syl_candidates"] == ["song.SYL"]


def test_render_track_export_all_formats(tmp_path, monkeypatch):
    import app.audio_engine as engine
    source = tmp_path / "src.wav"; source.write_bytes(b"x")
    track = _track(1); track.volume_db = -3; track.pan = 0.2
    monkeypatch.setattr(engine, "render_track", lambda track, source, out, apply_inserts=True: Path(out).write_bytes(b"wav"))
    seen = []
    monkeypatch.setattr(engine, "_run", lambda cmd: seen.append(cmd) or "")
    for fmt in ("wav", "mp3", "flac"):
        engine.render_track_export(track, source, tmp_path / f"out.{fmt}", fmt=fmt)
    assert any("pcm_s24le" in cmd for cmd in seen)
    assert any("libmp3lame" in cmd for cmd in seen)
    assert any("flac" in cmd for cmd in seen)
    with pytest.raises(ValueError):
        engine.render_track_export(track, source, tmp_path / "x.aac", fmt="aac")


def test_export_mta_merge_executes_slot_mix(tmp_path, monkeypatch):
    import app.codec as codec
    import app.storage as storage
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setattr(codec, "pdir", storage.pdir)
    p = storage.create_project("Merge", "MTA8")
    for i in range(2):
        (storage.pdir(p.id) / "audio" / f"t{i}.wav").write_bytes(b"src")
        p.tracks.append(_track(i))
    storage.save_project(p)
    monkeypatch.setattr(codec, "render_track", lambda track, source, out: Path(out).write_bytes(b"wav"))
    commands = []
    def fake_run(cmd):
        commands.append(cmd)
        if cmd and str(cmd[-1]).endswith('.wav'):
            Path(cmd[-1]).write_bytes(b"merged")
        elif cmd and str(cmd[-1]).endswith('.mta8'):
            Path(cmd[-1]).write_bytes(b"mta")
        return ""
    monkeypatch.setattr(codec, "run", fake_run)
    monkeypatch.setattr(codec, "normalize_matroska_for_mta", lambda source, target: target.write_bytes(b"normalized") or 0)
    monkeypatch.setattr(codec, "obfuscate_media_copy", lambda source, target, offset: target.write_bytes(b"mta") or target)
    monkeypatch.setattr(codec, "inspect_cluster_transport", lambda path: {"first_cluster_is_canonical": True} if path.name == "mta-layout.mka" else {"media_xor_validated": True})
    slots = [MtaSlotMapping(slot=1, name="Merged", type="drums", track_ids=["t0", "t1"])]
    out = storage.pdir(p.id) / "result.mta8"
    assert codec.export_mta(p, out, slots) == out
    assert any("amix=inputs=2" in " ".join(cmd) for cmd in commands)
    assert any("matroska" in cmd for cmd in commands)


def _fake_syl_with_sections() -> bytes:
    text_payload = b"\x00Demo title"
    frame = b"TIT2" + len(text_payload).to_bytes(4, "big") + b"\x00\x00" + text_payload
    padding = b"\x00" * 16
    colors_body = b"\x28\xb6\xa9" + (b"\x10" * 15) + (b"\x20" * 15)
    colors_header = b"COLORSBEGININD0000211LYR00927\r\n"
    colors = colors_header + colors_body
    colors += f"{len(colors_header) + len(colors_body):06d}".encode() + b"COLORS200\r\n"
    chords_body = b"X" * 30
    chords_header = b"CHORDSBEGININD0000211LYR00030\r\n"
    chords = chords_header + chords_body
    chords += f"{len(chords_header) + len(chords_body):06d}".encode() + b"CHORDS200\r\n"
    tail = padding + b"DELTABEGIN0DELTAEND\r\n" + colors + chords
    size = len(frame + tail)
    syn = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    return b"ID3\x03\x00\x00" + syn + frame + tail


def test_syl_section_and_colors_structure_analysis():
    from app.mta_reverse import inspect_embedded_id3
    info = inspect_embedded_id3(_fake_syl_with_sections())
    assert info["frames"][0]["text"] == "Demo title"
    assert info["delta"]["present"] is True
    colors = info["proprietary_sections"]["COLORS"]
    assert colors["colors_structure"]["binary_header_hex"] == "28b6a9"
    assert colors["colors_structure"]["record_size"] == 15
    assert colors["colors_structure"]["record_count"] == 2
    assert colors["colors_structure"]["normal_event_count"] == 1
    chords = info["proprietary_sections"]["CHORDS"]
    assert chords["declared_payload_size_matches_actual"] is True


def test_mtx_xml_analysis_note_on_duration_and_padding():
    from app.mta_reverse import inspect_mtx_xml
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
<MtxInfoData version="0.0"><Identity><UserId>1</UserId><AProId>0</AProId></Identity>
<General><BaseKey>11</BaseKey><BaseBpm>100</BaseBpm><DurataSec>3</DurataSec><PreCntUSec>2000000</PreCntUSec></General>
<TrkAudio><Track><Num>1</Num><Nome>Piano</Nome><Type>KEYBOARD</Type><Routing>1</Routing><Volume>100</Volume><MuteSolo>0</MuteSolo><NoteOn>1;0;1</NoteOn></Track></TrkAudio></MtxInfoData>\n""" + b"\x00" * 1000
    info = inspect_mtx_xml(xml)
    assert info["general"]["duration_sec"] == 3
    assert info["padding_size"] == 1000
    assert info["padding_all_zero"] is True
    assert info["tracks"][0]["note_on_count"] == 3
    assert info["tracks"][0]["note_on_active_count"] == 2
    assert info["tracks"][0]["note_on_matches_duration_seconds"] is True


def test_attachment_extraction_uses_ebml_fallback(tmp_path, monkeypatch):
    import app.mta_reverse as rev
    src = tmp_path / "broken-ebml.mta"
    src.write_bytes(b"not-used")
    info = {
        "streams": [{"index": 12, "codec_type": "attachment", "extradata_size": 4, "tags": {"filename": "x.syl"}}],
        "format": {"format_name": "matroska,webm"},
    }
    monkeypatch.setattr(rev, "probe", lambda path: info)
    monkeypatch.setattr(rev, "_run", lambda cmd: (_ for _ in ()).throw(RuntimeError("ffmpeg failed")))
    monkeypatch.setattr(rev, "_scan_matroska_filedata", lambda path, sizes: [b"ID3\x00"])
    out = rev.extract_attachments(src, tmp_path / "out")
    assert len(out) == 1
    assert out[0]["extraction_method"] == "ebml-filedata-fallback"
    assert out[0]["filename"] == "x.syl"


def test_observed_colors_decoder_recovers_timing_and_highlight_position():
    from app.mta_reverse import _decode_colors_observed
    key = bytes((i * 73 + 19) & 0xFF for i in range(256))
    assert len(set(key)) == 256
    events = []
    minute = 0
    source = [
        (475, 127, 0),
        (1101, 3, 0),
        (1638, 6, 0),
        (5999, 9, 1),
    ]
    for i in range(257):
        if i < len(source):
            centiseconds, position, next_minute = source[i]
        else:
            centiseconds, position, next_minute = (1200 + i) % 6000, (i % 90), minute
        plain = bytearray(b"\x0a\x00\x00\x1e\x00\x00m\x00\x00\x00=:k\x00\x00")
        digits = [int(x) for x in f"{centiseconds:04d}"]
        plain[1], plain[2], plain[4], plain[5] = digits
        pdigits = [int(x) for x in f"{position:03d}"]
        plain[7], plain[8], plain[9] = pdigits
        plain[14] = next_minute
        rec = bytearray(15)
        for j, value in enumerate(plain):
            phase = (i - 17 * j) % 256
            rec[j] = value ^ key[phase] ^ 0x0A
        events.append(bytes(rec))
        minute = next_minute
    terminal = b"\x00" * 15
    body = b"\x28\xb6\xa9" + b"".join(events) + terminal
    report = _decode_colors_observed(body)
    assert report["validated"] is True
    assert report["keystream_is_complete_permutation"] is True
    assert report["events"][0]["time_ms"] == 4750
    assert report["events"][0]["highlight_position"] == 127
    assert report["events"][1]["highlight_position"] == 3
    assert report["events"][3]["next_minute_block"] == 1


def test_observed_variable_section_decoder_recovers_records_and_text():
    from app.mta_reverse import _decode_variable_section_observed
    key_prime = [(i * 29 + 7) & 0xFF for i in range(256)]
    records = [
        b"\n\x00\x01\x1e\x02\x03m" + bytes(c ^ 0x30 for c in b"Demo") + b"0" + b"=:k\x00\x00",
        b"\n\x00\x01\x1e\x02\x04m" + bytes(c ^ 0x30 for c in b"Line") + b"0" + b"=:k\x00\x01",
    ]
    plain = b"".join(records) + b"=:0=:"
    cipher = bytes(
        value ^ key_prime[(239 * offset) % 256] ^ 0x0A
        for offset, value in enumerate(plain)
    )
    report = _decode_variable_section_observed(b"\x28\xb6\xa9" + cipher, key_prime, section="LYRICS")
    assert report["validated"] is True
    assert report["record_count"] == 2
    assert report["records"][0]["text"] == "Demo"
    assert report["records"][1]["text"] == "Line"
    assert report["records"][0]["decimal_index_candidate"] == 123
    assert report["records"][1]["decimal_index_candidate"] == 124
    assert report["records"][1]["next_minute_block"] == 1
    assert report["records"][0]["time_ms"] == 1230
    assert report["records"][1]["time_ms"] == 1240
    assert report["timing_monotonic"] is True
    assert report["terminal_marker_present"] is True


def test_miditk_decoder_reconstructs_standard_midi():
    from app.mta_reverse import _decode_miditk_observed, decode_miditk_to_midi
    key = bytes((i * 73 + 19) & 0xFF for i in range(256))
    assert len(set(key)) == 256
    track = (
        b"\x00\xff\x51\x03\x07\xa1\x20"  # tempo 120 BPM
        b"\x00\xff\x06\x05Intro"
        b"\x83\x60\xff\x06\x06Verse1"
        b"\x00\xff\x2f\x00"
    )
    midi = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0" + b"MTrk" + len(track).to_bytes(4, "big") + track
    body = bytes(
        value ^ key[(239 * (offset - 3)) % 256] ^ 0x0A ^ 0x30
        for offset, value in enumerate(midi)
    )
    assert decode_miditk_to_midi(body, list(key)) == midi
    report = _decode_miditk_observed(body, list(key))
    assert report["validated"] is True
    assert report["decoded_magic"] == "MThd"
    assert report["format"] == 0
    assert report["track_count"] == 1
    assert report["ppq"] == 480
    assert report["tracks"][0]["length_matches"] is True
    assert [m["text"] for m in report["markers"]] == ["Intro", "Verse1"]


def test_mta_miditk_download_route_uses_verified_sidecar(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("MIDI source")
    analysis_dir = storage.pdir(project.id) / "attachments" / "reverse-analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    midi = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0MTrk\x00\x00\x00\x04\x00\xff\x2f\x00"
    (analysis_dir / "01-song.miditk.mid").write_bytes(midi)
    client = TestClient(main.app, headers=WRITE_HEADERS)
    response = client.get(f"/api/projects/{project.id}/mta-miditk")
    assert response.status_code == 200
    assert response.content == midi
    assert response.headers["content-type"].startswith("audio/midi")


def test_decode_miditk_from_wrapped_syl_sections():
    from app.mta_reverse import decode_miditk_from_syl

    key = bytes((i * 73 + 19) & 0xFF for i in range(256))
    color_records = []
    for i in range(257):
        plain = bytearray(b"\x0a\x00\x00\x1e\x00\x00m\x00\x00\x00=:k\x00\x00")
        value = (100 + i) % 6000
        digits = [int(x) for x in f"{value:04d}"]
        plain[1], plain[2], plain[4], plain[5] = digits
        position = i % 90
        pdigits = [int(x) for x in f"{position:03d}"]
        plain[7], plain[8], plain[9] = pdigits
        rec = bytes(
            byte ^ key[(i - 17 * j) % 256] ^ 0x0A
            for j, byte in enumerate(plain)
        )
        color_records.append(rec)
    colors_body = b"\x28\xb6\xa9" + b"".join(color_records) + (b"\x00" * 15)

    track = b"\x00\xff\x06\x05Intro\x00\xff\x2f\x00"
    midi = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0" + b"MTrk" + len(track).to_bytes(4, "big") + track
    miditk_body = bytes(
        byte ^ key[(239 * (offset - 3)) % 256] ^ 0x0A ^ 0x30
        for offset, byte in enumerate(midi)
    )

    wrapped = (
        b"COLORSBEGININD0000211LYR00927\r\n" + colors_body + b"000000COLORS200\r\n"
        + b"MIDITKBEGININD0000211LYR00927\r\n" + miditk_body + b"000000MIDITK200\r\n"
    )
    assert decode_miditk_from_syl(wrapped) == midi
    assert decode_miditk_from_syl(b"no proprietary sections") is None


def test_cluster_transport_uses_seekhead_and_cues_to_locate_noncanonical_media(tmp_path):
    from app.mta_reverse import inspect_cluster_transport

    def size_vint(n: int) -> bytes:
        for length in range(1, 9):
            if n < (1 << (7 * length)) - 1:
                marker = 1 << (7 * length)
                return (marker | n).to_bytes(length, "big")
        raise ValueError(n)

    def elem(element_id: bytes, payload: bytes) -> bytes:
        return element_id + size_vint(len(payload)) + payload

    cluster_id = bytes.fromhex("1f43b675")

    def seek_head(cluster_rel: int) -> bytes:
        seek = elem(b"\x53\xab", cluster_id) + elem(b"\x53\xac", cluster_rel.to_bytes(4, "big"))
        return elem(bytes.fromhex("114d9b74"), elem(b"\x4d\xbb", seek))

    def cues(cluster_rel: int) -> bytes:
        track_positions = elem(b"\xf7", b"\x01") + elem(b"\xf1", cluster_rel.to_bytes(4, "big"))
        point = elem(b"\xb3", b"\x00") + elem(b"\xb7", track_positions)
        return elem(bytes.fromhex("1c53bb6b"), elem(b"\xbb", point))

    # Fixed-width Seek/Cue positions make the element lengths stable, so one
    # iteration is enough to resolve the relative media offset.
    sh = seek_head(0)
    cq = cues(0)
    media_rel = len(sh) + len(cq)
    sh = seek_head(media_rel)
    cq = cues(media_rel)
    media = bytes.fromhex("0fb2f7b0") + b"\x00" * 28
    segment_payload = sh + cq + media
    segment = bytes.fromhex("18538067") + size_vint(len(segment_payload)) + segment_payload
    ebml = bytes.fromhex("1a45dfa3") + size_vint(8) + b"matroska"
    src = tmp_path / "sample.mta"
    src.write_bytes(ebml + segment)

    report = inspect_cluster_transport(src)
    assert report["validated"] is True
    assert report["cue_positions_match_seek_cluster"] is True
    assert report["first_media_magic_hex"] == "0fb2f7b0"
    assert report["first_cluster_is_canonical"] is False
    assert report["noncanonical_cluster_transport"] is True
