"""Opt-in real pinned Basic Pitch inference/receipt through the pull protocol.

Uses an already installed reviewed interpreter; never downloads model weights.
"""
import io
import json
import os
from pathlib import Path
import wave

import numpy as np
import pytest

from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401
from test_r210_pull_coordinator import authority as authority, DirectClient, economic, task  # noqa: F401


@pytest.mark.skipif(not os.getenv('MTA_STUDIO_PYTHON'),reason='Needs the existing reviewed Basic Pitch runtime and pinned weights')
def test_real_basic_pitch_load_receipt_original_ledger_and_no_repeat(authority,monkeypatch):
    from app import ai_pull_coordinator as central,ai_pull_worker as worker
    from app.ai_studio_adapter import MODEL_SHA256
    from app.ai_model_attestation import SCHEMA
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','basic-pitch-v1')
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_BASIC_PITCH_EXECUTABLE',str(Path(__file__).resolve().parents[1]/'app/ai_studio_adapter.py'))
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_BASIC_PITCH_PYTHON',os.environ['MTA_STUDIO_PYTHON'])
    node=central.register('real-basic-pitch-receipt',['audio-to-midi-basic-pitch'])
    rate=44100;t=np.arange(rate*2)/rate
    audio=(np.sin(2*np.pi*440*t)*.2*32767).astype('<i2').tobytes()
    source=io.BytesIO()
    with wave.open(source,'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(audio)
    job=central.enqueue(authority[0],'audio-to-midi-basic-pitch',{},source_wav=source.getvalue(),timeout_seconds=240)
    client=DirectClient(node['credential']);state=authority[2]/'real-model-state'
    assert worker.run_once(client,state)
    assert economic(job)==('done','finished','closed')
    proof=json.loads(task(job)['completion_json']);receipt=proof['model_receipt']
    assert receipt['schema']==SCHEMA and receipt['model_sha256']==MODEL_SHA256
    assert receipt['context']['job_id']==job and receipt['pid']>0
    assert proof['cpu_seconds']>0 and proof['media_type']=='application/zip'
    assert not worker.run_once(client,state)
    assert json.loads(task(job)['completion_json'])==proof
