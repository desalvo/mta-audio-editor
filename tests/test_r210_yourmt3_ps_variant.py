"""Variant identity and publication guards, independent of real inference tests."""
import json
import sys
import pytest
from app.yourmt3_adapter import selected_variant,MODEL,part_identity
from app import studio_catalog
from app.studio_checkpoint import convert
from scripts.install_studio_yourmt3_ps import publish


def test_default_variant_remains_backward_compatible_and_unknown_variant_fails(monkeypatch):
    monkeypatch.delenv('MTA_STUDIO_YOURMT3_VARIANT',raising=False)
    assert selected_variant()[0]==MODEL and selected_variant()[2]=='mta-runtime.json'
    monkeypatch.setenv('MTA_STUDIO_YOURMT3_VARIANT','unreviewed')
    with pytest.raises(ValueError):selected_variant()


def test_ps_is_available_only_after_its_own_inference_receipt(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_STUDIO_YOURMT3_VARIANT','ps')
    monkeypatch.setenv('MTA_STUDIO_YOURMT3_RUNTIME',str(tmp_path))
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON',sys.executable)
    (tmp_path/'mta-runtime.json').write_text(json.dumps({'model':MODEL,'tested':True}))
    assert studio_catalog.python_for('audio-to-midi-yourmt3') is None
    path=tmp_path/'mta-runtime-ps.json';path.write_text(json.dumps({'model':selected_variant()[0],'tested':False}))
    assert studio_catalog.python_for('audio-to-midi-yourmt3') is None
    path.write_text(json.dumps({'model':selected_variant()[0],'tested':True}))
    # Metadata alone cannot authorize the upstream source selected by PS.
    assert studio_catalog.python_for('audio-to-midi-yourmt3') is None


def test_ps_converter_does_not_accept_arbitrary_checkpoints(tmp_path):
    source=tmp_path/'anything.ckpt';source.write_bytes(b'not reviewed')
    with pytest.raises(ValueError,match='size'):convert(source,tmp_path/'out.safetensors','ps')
    assert not (tmp_path/'out.safetensors').exists()


def test_initial_receipt_publication_cannot_replace_an_existing_variant(tmp_path):
    path=tmp_path/'receipt.json';path.write_text('keep')
    with pytest.raises(FileExistsError):publish(path,{'tested':True},exclusive=True)
    assert path.read_text()=='keep' and len(list(tmp_path.iterdir()))==1


def test_singing_classes_are_not_mislabeled_as_gm_fx_instruments():
    assert part_identity(False,100)==('Singing voice','singing-voice',53)
    assert part_identity(False,101)==('Singing chorus','singing-chorus',52)
    assert part_identity(False,0)==('GM 1','gm-0',0)
    assert part_identity(True,0)==('Drums','drums',None)
