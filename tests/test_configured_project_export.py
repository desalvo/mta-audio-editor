from pathlib import Path
import sys
import types


def test_export_dialog_asks_name_and_format_specific_parameters():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    assert "Esporta progetto" in js
    assert 'id="exportFileName"' in js
    assert 'id="exportSampleRate"' in js
    assert 'id="exportWavBits"' in js
    assert 'id="exportMp3Bitrate"' in js
    assert 'id="exportFlacCompression"' in js
    assert "confirmConfiguredExport" in js
    assert "executeConfiguredExport" in js
    assert "/configured-export" in js


def test_native_export_asks_filesystem_destination():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    native = (root / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")

    assert "choose_export_save_path" in js
    assert "def choose_export_save_path(self, suggested_name: str, extension: str)" in native
    assert "FileDialog.SAVE" in native


def test_configured_export_request_model_contains_audio_parameters():
    from app.models import ProjectExportRequest

    request = ProjectExportRequest(
        format="wav",
        filename="mix",
        sample_rate=48000,
        wav_bit_depth=32,
    )
    assert request.sample_rate == 48000
    assert request.wav_bit_depth == 32
    assert request.mp3_bitrate_kbps == 320
    assert request.flac_compression == 8


def test_native_export_dialog_extension_validation(tmp_path, monkeypatch):
    from native.mta_audio_editor_native import NativeApi

    fake_webview = types.SimpleNamespace(FileDialog=types.SimpleNamespace(SAVE="save"))
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    class Window:
        def create_file_dialog(self, *_args, **_kwargs):
            return str(tmp_path / "master")

    api = NativeApi()
    api.window = Window()
    result = api.choose_export_save_path("master", "wav")
    assert result["ok"] is True
    assert result["path"].endswith(".wav")
