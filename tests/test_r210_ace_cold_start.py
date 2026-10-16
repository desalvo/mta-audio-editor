"""A cold ACE HTTP control timeout must not cancel a healthy accepted job."""
from __future__ import annotations
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from app import ace_step_http_worker as worker


def audio():
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(44100)
        wav.writeframes(b'\0\0' * 441)
    return stream.getvalue()


def staged(tmp_path, budget=3600):
    (tmp_path / 'inputs').mkdir()
    (tmp_path / 'inputs/source.wav').write_bytes(audio())
    plan = tmp_path / 'request.json'
    plan.write_text(json.dumps({'model_id': 'ace-step-1.5', 'prompt': 'orchestral',
        'inference_timeout_seconds': budget, 'source_audio': [{'filename': 'inputs/source.wav'}]}))
    return plan


@pytest.mark.parametrize('standalone', [False, True])
def test_real_http_cold_control_takes_more_than_three_seconds_without_cancel(tmp_path, monkeypatch, standalone):
    plan = staged(tmp_path)
    seen = []
    data = audio()
    class API(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass
        def reply(self, body):
            self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            seen.append((self.path, json.loads(body) if self.path.endswith('/control') else None))
            if self.path == '/release_task':
                self.reply(b'{"data":{"task_id":"cold-task"}}')
            elif self.path.endswith('/control'):
                if not json.loads(body).get('cancel'):
                    time.sleep(3.25)  # Reproduces the old 3-second socket limit.
                self.reply(b'{"task_id":"cold-task","state":"running","cancel_requested":false}')
            else:
                assert self.path == '/query_result'
                self.reply(json.dumps({'data': [{'task_id': 'cold-task', 'status': 1,
                    'result': [{'file': '/v1/audio?result=1'}]}]}).encode())
        def do_GET(self):
            if self.path.startswith('/mta/telemetry/'):
                self.send_response(404); self.end_headers()
            else:
                assert self.path == '/v1/audio?result=1'
                self.reply(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), API)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv('MTA_ACE_STEP_URL', f'http://127.0.0.1:{server.server_port}')
    monkeypatch.setenv('MTA_AI_PROGRESS_FILE', str(tmp_path / 'progress.json'))
    monkeypatch.delenv('MTA_ACE_STEP_PID', raising=False)
    monkeypatch.setattr(worker, 'AceProcessMeter', lambda *a: SimpleNamespace(sample=lambda: {}))
    output = tmp_path / 'output.wav'
    try:
        if standalone:
            result = subprocess.run([sys.executable, str(Path(worker.__file__).resolve()),
                '--request', str(plan), '--output', str(output)], cwd=tmp_path,
                env={**os.environ, 'PYTHONPATH': ''}, capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, result.stderr
        else:
            worker.run(plan, output)
        assert output.read_bytes() == data
        assert [path for path, body in seen].count('/release_task') == 1
        assert [body for path, body in seen if path.endswith('/control')] == [
            {'cancel': False, 'timeout_seconds': 3600}]
        assert json.loads((tmp_path / 'progress.json').read_text())['phase'] == 'completed'
    finally:
        server.shutdown(); server.server_close(); thread.join(3)


@pytest.mark.parametrize('phase', ['control', 'poll'])
@pytest.mark.parametrize('error', ['socket', 'connection', '503', '429'])
def test_retryable_failures_preserve_task_and_budget(tmp_path, monkeypatch, phase, error):
    plan = staged(tmp_path)
    clock = [0]
    attempts = [0]
    controls, submits, queries = [], [], []
    def request(url, data=None, *args, **kwargs):
        if url.endswith('/release_task'):
            submits.append(url)
            return b'{"data":{"task_id":"task"}}'
        failing = (phase == 'control' and url.endswith('/control')) or (phase == 'poll' and url.endswith('/query_result'))
        if url.endswith('/control'):
            controls.append(json.loads(data))
        if url.endswith('/query_result'):
            queries.append(url)
        if failing and attempts[0] < 2:
            attempts[0] += 1
            clock[0] += 30
            if error == 'socket':
                raise TimeoutError('secret=DO_NOT_COPY')
            if error == 'connection':
                raise URLError('secret=DO_NOT_COPY')
            raise HTTPError(url, int(error), 'secret=DO_NOT_COPY', None, None)
        if url.endswith('/control'):
            return b'{"task_id":"task","state":"running"}'
        if url.endswith('/query_result'):
            return b'{"data":[{"task_id":"task","status":1,"result":[{"file":"/v1/audio?x"}]}]}'
        if '/v1/audio?' in url:
            return audio()
        return b'{}'
    monkeypatch.setattr(worker, '_request', request)
    monkeypatch.setattr(worker, 'time', SimpleNamespace(monotonic=lambda: clock[0], sleep=lambda delay: clock.__setitem__(0, clock[0] + delay)))
    monkeypatch.setattr(worker, 'AceProcessMeter', lambda *a: SimpleNamespace(sample=lambda: {}))
    progress = tmp_path / 'progress.json'; monkeypatch.setenv('MTA_AI_PROGRESS_FILE', str(progress))
    worker.run(plan, tmp_path / 'output.wav')
    assert len(submits) == 1 and len(queries) >= 1
    assert attempts[0] == 2 and clock[0] == 64
    assert controls and all(body == {'cancel': False, 'timeout_seconds': 3600} for body in controls)
    assert 'DO_NOT_COPY' not in progress.read_text()


def test_unresponsive_control_stops_at_total_budget_then_requests_cancel(tmp_path, monkeypatch):
    plan = staged(tmp_path, 60)
    clock = [0]
    controls, timeouts = [], []
    def request(url, data=None, *args, **kwargs):
        if url.endswith('/release_task'):
            return b'{"data":{"task_id":"task"}}'
        if url.endswith('/control'):
            body = json.loads(data); controls.append(body)
            if body.get('cancel'):
                return b'{"task_id":"task","cancel_requested":true}'
            timeouts.append(kwargs['timeout']); clock[0] += kwargs['timeout']
            raise TimeoutError('backend still loading')
        pytest.fail('No query or resubmission before control completes')
    monkeypatch.setattr(worker, '_request', request)
    monkeypatch.setattr(worker, 'time', SimpleNamespace(monotonic=lambda: clock[0], sleep=lambda delay: clock.__setitem__(0, clock[0] + delay)))
    monkeypatch.setattr(worker, 'AceProcessMeter', lambda *a: SimpleNamespace(sample=lambda: {}))
    with pytest.raises(RuntimeError, match='generation timed out'):
        worker.run(plan, tmp_path / 'output.wav')
    assert clock[0] == 54 and timeouts == [30, 22]
    assert controls[-1] == {'cancel': True}
    assert not (tmp_path / 'output.wav').exists()


@pytest.mark.parametrize('code', [401, 403, 422])
def test_control_auth_and_validation_errors_still_fail_closed(tmp_path, monkeypatch, code):
    plan = staged(tmp_path)
    seen = []
    def request(url, data=None, *args, **kwargs):
        if url.endswith('/release_task'):
            return b'{"data":{"task_id":"task"}}'
        seen.append(json.loads(data))
        raise HTTPError(url, code, 'denied', None, None)
    monkeypatch.setattr(worker, '_request', request)
    monkeypatch.setattr(worker, 'AceProcessMeter', lambda *a: SimpleNamespace(sample=lambda: {}))
    with pytest.raises(RuntimeError, match='control request rejected'):
        worker.run(plan, tmp_path / 'output.wav')
    assert seen == [{'cancel': False, 'timeout_seconds': 3600}, {'cancel': True}]
    assert not (tmp_path / 'output.wav').exists()
