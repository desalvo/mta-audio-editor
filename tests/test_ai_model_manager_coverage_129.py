from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


def _fake_whisper(monkeypatch, tmp_path):
    mod = types.ModuleType("whisper")
    mod._MODELS = {
        "tiny": "https://example.invalid/tiny.pt",
        "large-v3": "https://example.invalid/large-v3.pt",
    }

    class Model:
        pass

    def load_model(model_id, download_root):
        Path(download_root).mkdir(parents=True, exist_ok=True)
        filename = Path(mod._MODELS[model_id]).name
        (Path(download_root) / filename).write_bytes(b"weights")
        return Model()

    mod.load_model = load_model
    monkeypatch.setitem(sys.modules, "whisper", mod)
    return mod


def _fake_madmom(monkeypatch):
    modules = {
        "madmom_infer": types.ModuleType("madmom_infer"),
        "madmom_infer.audio": types.ModuleType("madmom_infer.audio"),
        "madmom_infer.audio.chroma": types.ModuleType("madmom_infer.audio.chroma"),
        "madmom_infer.features": types.ModuleType("madmom_infer.features"),
        "madmom_infer.features.chords": types.ModuleType("madmom_infer.features.chords"),
    }

    class Dummy:
        def __init__(self):
            pass

    modules["madmom_infer.audio.chroma"].DeepChromaProcessor = Dummy
    modules["madmom_infer.features.chords"].DeepChromaChordRecognitionProcessor = Dummy
    modules["madmom_infer.features.chords"].CNNChordFeatureProcessor = Dummy
    modules["madmom_infer.features.chords"].CRFChordRecognitionProcessor = Dummy
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def test_lyrics_catalog_download_delete_and_validation(monkeypatch, tmp_path):
    import app.ai_models as m

    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_LYRICS_MODEL_DIR", raising=False)
    fake = _fake_whisper(monkeypatch, tmp_path)
    real_find_spec = m.importlib.util.find_spec
    monkeypatch.setattr(m.importlib.util, "find_spec", lambda name: object() if name == "whisper" else real_find_spec(name))

    catalog = m.lyrics_catalog(native=True)
    assert catalog["storage"] == "local"
    assert catalog["on_demand"] is True
    assert next(x for x in catalog["models"] if x["id"] == "tiny")["installed"] is False

    installed = m.download_lyrics_model("tiny", native=True)
    assert installed["installed"] is True
    assert installed["filename"] == "tiny.pt"

    removed = m.delete_lyrics_model("tiny", native=True)
    assert removed == {"ok": True, "model_id": "tiny", "removed": True, "storage": "local"}
    assert m.delete_lyrics_model("tiny")["removed"] is False

    with pytest.raises(ValueError):
        m.download_lyrics_model("nope")
    with pytest.raises(ValueError):
        m.delete_lyrics_model("nope")

    monkeypatch.setattr(m.importlib.util, "find_spec", lambda name: None if name == "whisper" else real_find_spec(name))
    with pytest.raises(RuntimeError):
        m.download_lyrics_model("tiny")

    fake._MODELS.pop("tiny")
    assert m._whisper_filename("tiny") is None
    monkeypatch.delitem(sys.modules, "whisper", raising=False)
    assert m._whisper_filename("tiny") is None


def test_chord_catalog_availability_snapshot_and_validation(monkeypatch, tmp_path):
    import app.ai_models as m

    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    real_find_spec = m.importlib.util.find_spec
    monkeypatch.setattr(m.importlib.util, "find_spec", lambda name: object() if name.startswith("madmom_infer") else real_find_spec(name))
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/sonic-annotator" if name == "sonic-annotator" else None)

    assert m.chord_engine_available("madmom-deep-chroma") is True
    assert m.chord_engine_available("madmom-cnn-crf") is True
    assert m.chord_engine_available("chordino") is True
    assert m.chord_engine_available("mta-chromagram") is True
    assert m.chord_engine_available("unknown") is False

    catalog = m.chords_catalog(native=True)
    assert catalog["storage"] == "local"
    assert all("available" in e for e in catalog["engines"])

    assert m._cache_snapshot() == set()
    root = m._chord_cache_root()
    (root / "nested").mkdir(parents=True)
    (root / "nested" / "weight.bin").write_bytes(b"x")
    assert m._cache_snapshot() == {"nested/weight.bin"}

    with pytest.raises(ValueError):
        m.download_chord_model("nope")
    with pytest.raises(ValueError):
        m.delete_chord_model("nope")

    monkeypatch.setattr(m.importlib.util, "find_spec", lambda name: None if name == "madmom_infer" else real_find_spec(name))
    with pytest.raises(RuntimeError):
        m.download_chord_model("madmom-deep-chroma-crf")


def test_chord_model_downloads_and_safe_delete(monkeypatch, tmp_path):
    import app.ai_models as m

    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    _fake_madmom(monkeypatch)
    real_find_spec = m.importlib.util.find_spec
    monkeypatch.setattr(m.importlib.util, "find_spec", lambda name: object() if name.startswith("madmom_infer") else real_find_spec(name))

    snapshots = [set(), {"deep.bin"}, {"deep.bin"}, {"deep.bin", "cnn.bin"}]
    monkeypatch.setattr(m, "_cache_snapshot", lambda: snapshots.pop(0))

    deep = m.download_chord_model("madmom-deep-chroma-crf", native=False)
    assert deep["installed"] is True
    cnn = m.download_chord_model("madmom-cnn-crf", native=True)
    assert cnn["installed"] is True

    root = m._chord_cache_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "deep.bin").write_bytes(b"deep")
    result = m.delete_chord_model("madmom-deep-chroma-crf")
    assert result["removed"] == ["deep.bin"]
    assert not (root / "deep.bin").exists()

    marker = m._chord_marker("madmom-cnn-crf")
    marker.write_text('{"files":["../escape.bin","cnn.bin"]}', encoding="utf-8")
    (root / "cnn.bin").write_bytes(b"cnn")
    result = m.delete_chord_model("madmom-cnn-crf", native=True)
    assert result["storage"] == "local"
    assert result["removed"] == ["cnn.bin"]
    assert not marker.exists()

    # Corrupt marker is tolerated and removed without touching unrelated files.
    marker = m._chord_marker("madmom-cnn-crf")
    marker.write_text("not-json", encoding="utf-8")
    assert m.delete_chord_model("madmom-cnn-crf")["removed"] == []
