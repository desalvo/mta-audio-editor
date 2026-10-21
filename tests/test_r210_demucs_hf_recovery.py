"""Real filesystem cache identity checks; no simulated neural inference."""
import pytest
from app.demucs_runtime import checkpoint_fingerprints


def cache(tmp_path,monkeypatch):
    monkeypatch.setenv('HF_HUB_CACHE',str(tmp_path))
    repo=tmp_path/'models--adefossez--HTDemucs'
    (repo/'refs').mkdir(parents=True);(repo/'refs/main').write_text('a'*40)
    snapshot=repo/'snapshots'/('a'*40);snapshot.mkdir(parents=True)
    (snapshot/'htdemucs.yaml').write_text('models: [955717e8]\n')
    (snapshot/'955717e8.safetensors').write_bytes(b'checkpoint identity test only')
    return repo,snapshot


def test_active_weight_and_reference_changes_invalidate_identity(tmp_path,monkeypatch):
    repo,snapshot=cache(tmp_path,monkeypatch)
    before=checkpoint_fingerprints('htdemucs')
    (snapshot/'955717e8.safetensors').write_bytes(b'changed checkpoint bytes')
    assert checkpoint_fingerprints('htdemucs')!=before
    (repo/'refs/main').write_text('b'*40)
    with pytest.raises(ValueError,match='snapshot'):checkpoint_fingerprints('htdemucs')


def test_canonical_hf_blob_links_are_supported_but_escape_is_refused(tmp_path,monkeypatch):
    repo,snapshot=cache(tmp_path,monkeypatch);weight=snapshot/'955717e8.safetensors'
    (repo/'blobs').mkdir();blob=repo/'blobs/weight';weight.rename(blob);weight.symlink_to(blob)
    assert '955717e8.safetensors' in checkpoint_fingerprints('htdemucs')
    outside=tmp_path/'outside';outside.write_bytes(b'not in this model repository')
    weight.unlink();weight.symlink_to(outside)
    with pytest.raises(ValueError,match='Unsafe'):checkpoint_fingerprints('htdemucs')


def test_uninstalled_model_is_not_confused_with_installed_snapshot(tmp_path,monkeypatch):
    cache(tmp_path,monkeypatch)
    assert checkpoint_fingerprints('htdemucs_ft')=={}
    with pytest.raises(ValueError):checkpoint_fingerprints('../weights')
