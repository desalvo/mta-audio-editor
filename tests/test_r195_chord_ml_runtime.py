import io
import json
import zipfile
from pathlib import Path

import pytest

from app import chord_ml


def _zip_bytes(files: dict[str, bytes | str]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content if isinstance(content, bytes) else content.encode())
    return bio.getvalue()


def test_model_root_and_install_delete(monkeypatch, tmp_path):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    assert chord_ml.model_root() == tmp_path / ".cache" / "chord-ml"
    root = chord_ml.model_dir("btc-hcqt")
    root.mkdir(parents=True)
    assert not chord_ml.installed("btc-hcqt")
    (root / ".mta-installed.json").write_text("{}")
    assert chord_ml.installed("btc-hcqt")
    assert chord_ml.delete_model("btc-hcqt") is True
    assert chord_ml.delete_model("btc-hcqt") is False


def test_safe_extract_rejects_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../oops", "x")
    with zipfile.ZipFile(archive) as zf:
        with pytest.raises(RuntimeError):
            chord_ml._safe_extract(zf, tmp_path / "out")


def test_flatten_single_directory(tmp_path):
    root = tmp_path / "root"; wrapper = root / "wrapper"; wrapper.mkdir(parents=True)
    (wrapper / "a.txt").write_text("a")
    chord_ml._flatten_single_directory(root)
    assert (root / "a.txt").read_text() == "a"


def test_download_btc_and_chordformer_with_fake_archives(monkeypatch, tmp_path):
    monkeypatch.setenv("MTA_CHORD_ML_MODEL_DIR", str(tmp_path / "models"))
    btc = _zip_bytes({"btc-hcqt-main/btc_hcqt_beatlesft.pt": b"pt", "btc-hcqt-main/hcqt_eval.py": "print('x')"})
    body = _zip_bytes({"BTC-ISMIR19-master/btc_model.py": "# body"})
    cf = _zip_bytes({**{f"ChordFormer-main/cache_data/fold{i}.sdict": b"x" for i in range(5)}, "ChordFormer-main/chord_recognition.py": "# infer"})
    def fake_download(url, dest):
        if "btc-hcqt" in url: data = btc
        elif "BTC-ISMIR19" in url: data = body
        else: data = cf
        dest.write_bytes(data)
    monkeypatch.setattr(chord_ml, "_download_zip", fake_download)
    info = chord_ml.download_model("btc-hcqt")
    assert info["id"] == "btc-hcqt" and chord_ml.installed("btc-hcqt")
    assert (chord_ml.model_dir("btc-hcqt") / "BTC-ISMIR19" / "btc_model.py").is_file()
    info = chord_ml.download_model("chordformer")
    assert info["id"] == "chordformer" and chord_ml.installed("chordformer")
    with pytest.raises(ValueError): chord_ml.download_model("missing")


def test_download_validates_missing_checkpoints(monkeypatch, tmp_path):
    monkeypatch.setenv("MTA_CHORD_ML_MODEL_DIR", str(tmp_path / "models"))
    weak = _zip_bytes({"repo/chord_recognition.py": "# no checkpoints"})
    monkeypatch.setattr(chord_ml, "_download_zip", lambda url, dest: dest.write_bytes(weak))
    with pytest.raises(RuntimeError, match="checkpoints"):
        chord_ml.download_model("chordformer")


def test_lab_and_json_parsers(tmp_path):
    lab = tmp_path / "x.lab"
    lab.write_text("0.0 1.0 C:maj\n1.0 2.0 A:min\n2.0 3.0 N\n")
    assert [(e.time_ms,e.chord) for e in chord_ml._lab_to_events(lab)] == [(0,"C"),(1000,"Am")]
    js = tmp_path / "x.json"
    js.write_text(json.dumps({"events":[{"start":0,"label":"G:maj"},{"start":1.5,"label":"D:min"}]}))
    assert [(e.time_ms,e.chord) for e in chord_ml._json_to_events(js)] == [(0,"G"),(1500,"Dm")]
    js.write_text(json.dumps([[0,"C:maj"],[1,"F:maj"]]))
    assert [e.chord for e in chord_ml._json_to_events(js)] == ["C","F"]


def test_run_success_and_failure(monkeypatch, tmp_path):
    class P:
        def __init__(self, rc): self.returncode=rc; self.stderr="boom"; self.stdout=""
    monkeypatch.setattr(chord_ml.subprocess, "run", lambda *a, **k: P(0))
    chord_ml._run(["x"], cwd=tmp_path)
    monkeypatch.setattr(chord_ml.subprocess, "run", lambda *a, **k: P(2))
    with pytest.raises(RuntimeError, match="boom"): chord_ml._run(["x"], cwd=tmp_path)


def test_extract_adapters_with_mocked_runner(monkeypatch, tmp_path):
    monkeypatch.setenv("MTA_CHORD_ML_MODEL_DIR", str(tmp_path / "models"))
    for model in ("btc-hcqt","chordformer"):
        root=chord_ml.model_dir(model);root.mkdir(parents=True);(root/".mta-installed.json").write_text("{}")
    monkeypatch.setattr(chord_ml, "runtime_available", lambda: True)
    audio=tmp_path/"a.wav";audio.write_bytes(b"x")
    def fake_run_btc(command, cwd, timeout=1800):
        out=Path(command[-1]);out.mkdir(exist_ok=True)
        (out/"results.json").write_text(json.dumps({"events":[{"start":0,"label":"C:maj"}]}))
    monkeypatch.setattr(chord_ml, "_run", fake_run_btc)
    assert chord_ml.extract_btc_hcqt(audio)[0].chord == "C"
    def fake_run_cf(command, cwd, timeout=1800):
        Path(command[3]).write_text("0 1 G:maj\n")
    monkeypatch.setattr(chord_ml, "_run", fake_run_cf)
    assert chord_ml.extract_chordformer(audio)[0].chord == "G"


def test_runtime_available_import_failure(monkeypatch):
    monkeypatch.setattr(chord_ml.importlib.util, "find_spec", lambda name: None if name == "torch" else object())
    assert chord_ml.runtime_available() is False
