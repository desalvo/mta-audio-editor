import os
from pathlib import Path
import pytest
from app.neural_vocal_adapter import checked_assets
from app.vocal_synthesis import Settings
from app.model_license_policy import selected


def test_settings_neural_explicit():
    assert Settings(backend='neural-external').backend=='neural-external'
    assert Settings().backend=='oddvoices'


def test_model_policy_not_oddvoices(monkeypatch):
    monkeypatch.delenv('MTA_NEURAL_SINGER_POLICY_MODEL',raising=False)
    assert selected('vocal-synthesis',{'settings':{'backend':'neural-external'}})=='unreviewed-neural-singer'
    monkeypatch.setenv('MTA_NEURAL_SINGER_POLICY_MODEL','diffsinger-qixuan')
    assert selected('vocal-synthesis',{'settings':{'backend':'neural-external'}})=='diffsinger-qixuan'


def test_missing_neural_assets_fail_closed(monkeypatch):
    for name in ('MTA_NEURAL_SINGER_EXECUTABLE','MTA_NEURAL_SINGER_CHECKPOINT','MTA_NEURAL_SINGER_SHA256'):
        monkeypatch.delenv(name,raising=False)
    with pytest.raises(RuntimeError):checked_assets()


def test_invalid_checkpoint_detected(tmp_path,monkeypatch):
    exe=tmp_path/'infer';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o700)
    model=tmp_path/'model.ckpt';model.write_bytes(b'invalid')
    monkeypatch.setenv('MTA_NEURAL_SINGER_EXECUTABLE',str(exe))
    monkeypatch.setenv('MTA_NEURAL_SINGER_CHECKPOINT',str(model))
    monkeypatch.setenv('MTA_NEURAL_SINGER_SHA256','a'*64)
    with pytest.raises(ValueError,match='integrity'):checked_assets()
