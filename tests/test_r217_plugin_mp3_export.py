from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MODELS = (ROOT / "app/models.py").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")
AUDIO = (ROOT / "app/audio_engine.py").read_text(encoding="utf-8")


def test_plugin_track_mp3_export_asks_parameters_before_destination():
    assert "function openTrackMp3ExportDialog(id)" in JS
    assert "Bitrate" in JS and "trackMp3Bitrate" in JS
    assert "trackMp3SampleRate" in JS
    assert "Metadata MP3 / ID3" in JS
    assert "trackMp3Title" in JS and "trackMp3Artist" in JS
    assert "trackMp3Album" in JS and "trackMp3Composer" in JS
    assert "trackMp3Genre" in JS and "trackMp3Date" in JS and "trackMp3Comment" in JS
    assert "if(ext==='mp3'&&!options){openTrackMp3ExportDialog(id);return}" in JS
    config = JS[JS.index("function confirmTrackMp3Export(id)"):JS.index("async function exportTrack", JS.index("function confirmTrackMp3Export(id)"))]
    assert "closeUtilityModal();void exportTrack(id,'mp3',options);" in config
    export = JS[JS.index("async function exportTrack"):JS.index("async function doExport", JS.index("async function exportTrack"))]
    assert export.index("choose_export_save_path") < export.index("track-export-jobs")


def test_track_export_api_carries_codec_settings_and_metadata():
    assert "class TrackExportRequest(BaseModel):" in MODELS
    assert "mp3_bitrate_kbps" in MODELS
    assert "metadata: dict[str, str]" in MODELS
    assert "body: TrackExportRequest | None = None" in MAIN
    worker = MAIN[MAIN.index("def _track_export_worker"):MAIN.index('@app.get("/api/media-jobs/{job_id}/download")')]
    assert 'bitrate=f"{int(req.mp3_bitrate_kbps)}k"' in worker
    assert "sample_rate=int(req.sample_rate)" in worker
    assert "metadata=req.metadata" in worker


def test_track_renderer_writes_id3_metadata_and_requested_bitrate():
    block = AUDIO[AUDIO.index("def render_track_export("):AUDIO.index("def auto_align_ms", AUDIO.index("def render_track_export(")) if "def auto_align_ms" in AUDIO[AUDIO.index("def render_track_export("):] else len(AUDIO)]
    assert '"-metadata", f"{key}={value}"' in block
    assert '"-b:a", bitrate' in block
    assert '"-id3v2_version", "3"' in block
    assert 'sample_rate: int = 44100' in block
