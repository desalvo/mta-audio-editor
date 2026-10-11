"""Exercise the actual ACE-Step HTTP request/poll/download path, not inference quality."""
from __future__ import annotations
import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app import ace_step_http_worker as worker


def _wav():
    data = io.BytesIO()
    with wave.open(data, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b'\x00\x00' * 4410)
    return data.getvalue()


def test_cover_http_roundtrip(monkeypatch, tmp_path):
    audio = _wav()
    seen = []
    class API(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            length = int(self.headers['Content-Length'])
            body = self.rfile.read(length)
            seen.append((self.path, body))
            if self.path == '/release_task':
                assert b'source.wav' in body and audio in body
                data = {'data': {'task_id': 'local-test'}}
            else:
                assert self.path == '/query_result'
                assert json.loads(body)['task_id_list'] == ['local-test']
                data = {'data': [{'task_id':'local-test', 'status':1, 'result':json.dumps([{'file':'/v1/audio?test=1'}])}]}
            payload = json.dumps(data).encode()
            self.send_response(200); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
        def do_GET(self):
            assert self.path == '/v1/audio?test=1'
            self.send_response(200); self.send_header('Content-Length',str(len(audio)));self.end_headers();self.wfile.write(audio)
    server=ThreadingHTTPServer(('127.0.0.1',0), API)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        monkeypatch.setenv('MTA_ACE_STEP_URL',f'http://127.0.0.1:{server.server_port}')
        root=tmp_path/'inputs';root.mkdir();(root/'track.wav').write_bytes(audio)
        plan=tmp_path/'request.json'
        plan.write_text(json.dumps({'model_id':'ace-step-1.5','operation':'remix','prompt':'orchestral transformation','strength':65,'source_audio':[{'filename':'inputs/track.wav'}]}))
        output=tmp_path/'preview.wav'
        worker.run(plan,output)
        assert output.read_bytes()==audio
        assert [route for route,_ in seen]==['/release_task','/query_result']
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def test_health_rejects_html(monkeypatch):
    from app.ace_step_http_worker import main
    import sys
    monkeypatch.setattr(worker,'_request',lambda *a,**kw:b'<html>ok</html>')
    monkeypatch.setattr(sys,'argv',['ace-step-worker','--check-server'])
    assert main()==1
