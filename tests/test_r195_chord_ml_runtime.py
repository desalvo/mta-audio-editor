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
    assert not chord_ml.installed("btc-hcqt")
    (root / "hcqt_eval.py").write_text("# infer")
    (root / "btc_hcqt_beatlesft.pt").write_bytes(b"fixture")
    (root / "BTC-ISMIR19").mkdir()
    (root / "BTC-ISMIR19" / "btc_model.py").write_text("# fixture")
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
    # Archive extraction unit test; all bytes below are synthetic. License
    # admission is covered independently and stays enabled in production.
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch,tmp_path,'chordformer')
    monkeypatch.setenv("MTA_CHORD_ML_MODEL_DIR", str(tmp_path / "models"))
    cf = _zip_bytes({**{f"ChordFormer-main/cache_data/fold{i}.sdict": b"x" for i in range(5)}, "ChordFormer-main/chord_recognition.py": "# infer"})
    calls = []
    def fake_download(url, dest):
        calls.append(url)
        dest.write_bytes(cf)
    monkeypatch.setattr(chord_ml, "_download_file", fake_download)
    with pytest.raises(RuntimeError, match="withdrawn"):
        chord_ml.download_model("btc-hcqt")
    assert calls == []
    info = chord_ml.download_model("chordformer")
    assert info["id"] == "chordformer" and chord_ml.installed("chordformer")
    with pytest.raises(ValueError): chord_ml.download_model("missing")


def test_download_validates_missing_checkpoints(monkeypatch, tmp_path):
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch,tmp_path,'chordformer')
    monkeypatch.setenv("MTA_CHORD_ML_MODEL_DIR", str(tmp_path / "models"))
    weak = _zip_bytes({"repo/chord_recognition.py": "# no checkpoints"})
    monkeypatch.setattr(chord_ml, "_download_file", lambda url, dest: dest.write_bytes(weak))
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


def test_extended_chord_labels_and_btc_master_result(tmp_path):
    lab = tmp_path / "x.lab"
    lab.write_text("0.0 1.0 C:maj7\n1.0 2.0 A:min7/E\n")
    assert [item.chord for item in chord_ml._lab_to_events(lab)] == ["Cmaj7", "Am7/E"]
    js = tmp_path / "x.json"
    js.write_text(json.dumps({"mta": {"master": [{"start": 0, "label": "C:maj7"}]}}))
    assert chord_ml._json_to_events(js)[0].chord == "Cmaj7"


def test_run_success_and_failure(monkeypatch, tmp_path):
    class P:
        def __init__(self, rc): self.returncode=rc; self.stderr="boom"; self.stdout=""
    monkeypatch.setattr(chord_ml.subprocess, "run", lambda *a, **k: P(0))
    chord_ml._run(["x"], cwd=tmp_path)
    monkeypatch.setattr(chord_ml.subprocess, "run", lambda *a, **k: P(2))
    with pytest.raises(RuntimeError, match="boom"): chord_ml._run(["x"], cwd=tmp_path)


def test_extract_adapters_with_mocked_runner(monkeypatch, tmp_path):
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch,tmp_path,'chordformer')
    authorize_fixture(monkeypatch,tmp_path,'btc-hcqt')
    monkeypatch.setenv("MTA_CHORD_ML_MODEL_DIR", str(tmp_path / "models"))
    for model in ("btc-hcqt","chordformer"):
        root=chord_ml.model_dir(model);root.mkdir(parents=True);(root/".mta-installed.json").write_text("{}")
    monkeypatch.setattr(chord_ml, "engine_available", lambda engine: True)
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


@pytest.mark.parametrize("mode", ["ok", "wrong-digest", "no-review", "bad-probe"])
def test_btc_replacement_install_is_bound_to_checkpoint_and_probe(monkeypatch, tmp_path, mode):
    import hashlib
    from types import SimpleNamespace
    from app import model_license_policy

    weight = b"replacement checkpoint fixture"
    digest = hashlib.sha256(weight).hexdigest()
    url = "https://example.test/hcqt.pt"
    monkeypatch.setenv("MTA_CHORD_ML_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("MTA_BTC_HCQT_CHECKPOINT_URL", url)
    monkeypatch.setenv("MTA_BTC_HCQT_CHECKPOINT_SHA256", digest)
    evidence = "https://example.test/review" + ("" if mode == "no-review" else "#sha256=" + digest)
    monkeypatch.setattr(model_license_policy, "evaluate_model", lambda _: SimpleNamespace(source=evidence))
    monkeypatch.setattr(chord_ml, "_require_safe_btc_torch", lambda: None)
    calls = []
    def download(source, destination):
        calls.append(source)
        fixtures = {
            chord_ml.BTC_CODE_ARCHIVE: _zip_bytes({"runtime/hcqt_eval.py": "# inference"}),
            **{chord_ml.BTC_BODY_CODE_URL + name: b"fixture code" for name in chord_ml.BTC_BODY_FILES},
            url: b"wrong checkpoint" if mode == "wrong-digest" else weight,
        }
        destination.write_bytes(fixtures[source])

    def probe(command, *, cwd, timeout, env_overrides):
        assert env_overrides["CUDA_VISIBLE_DEVICES"] == ""
        assert (cwd / chord_ml.BTC_CHECKPOINT).read_bytes() == weight
        assert {item.removeprefix(chord_ml.BTC_BODY_CODE_URL) for item in calls
                if item.startswith(chord_ml.BTC_BODY_CODE_URL)} == set(chord_ml.BTC_BODY_FILES)
        assert not list((cwd / "BTC-ISMIR19").rglob("*.pt"))
        output = Path(command[-1])
        output.mkdir()
        (output / "results-btc.json").write_text(json.dumps(
            {} if mode == "bad-probe" else {"mta": {"master": [{"start": 0, "end": 1, "label": "N"}]}}
        ))

    monkeypatch.setattr(chord_ml, "_download_file", download)
    monkeypatch.setattr(chord_ml, "_run", probe)
    if mode == "ok":
        result = chord_ml.download_model("btc-hcqt")
        assert result["checkpoint_sha256"] == digest
        assert chord_ml.installed("btc-hcqt")
        monkeypatch.setattr(chord_ml, "runtime_available", lambda: True)
        (chord_ml.model_dir("btc-hcqt") / chord_ml.BTC_CHECKPOINT).write_bytes(b"changed after install")
        with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
            chord_ml.extract_btc_hcqt(tmp_path / "music.wav")
    else:
        message = {"wrong-digest": "SHA-256 mismatch", "no-review": "authorization must identify",
                   "bad-probe": "failed the local inference probe"}[mode]
        with pytest.raises((RuntimeError, ValueError), match=message):
            chord_ml.download_model("btc-hcqt")
        assert not chord_ml.model_dir("btc-hcqt").exists()
        if mode == "no-review":
            assert calls == []
