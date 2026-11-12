"""Real library contracts for reviewed transport, audio and model-file updates."""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import socket
import threading
import time

import numpy as np
import pytest
import smart_open
import uvicorn
from websockets.asyncio.client import connect


@pytest.mark.parametrize('backend', ['websockets', 'websockets-sansio'])
def test_uvicorn_websocket_text_binary_and_clean_close(backend):
    async def echo(scope, receive, send):
        assert scope['type'] == 'websocket'
        assert (await receive())['type'] == 'websocket.connect'
        await send({'type': 'websocket.accept'})
        for key in ('text', 'bytes'):
            message = await receive()
            assert message['type'] == 'websocket.receive'
            await send({'type': 'websocket.send', key: message[key]})
        await send({'type': 'websocket.close', 'code': 1000})

    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    config = uvicorn.Config(echo, ws=backend, loop='asyncio', lifespan='off',
                            log_config=None, log_level='error', timeout_graceful_shutdown=1)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started

        async def client():
            async with connect(f'ws://127.0.0.1:{port}', open_timeout=3, close_timeout=3) as ws:
                payload = json.dumps({'op': 'midi', 'messages': [[144, 60, 100]], 'label': 'voce — été'})
                await ws.send(payload)
                assert await asyncio.wait_for(ws.recv(), 3) == payload
                binary = b'\x90\x3c\x64' + bytes(128)
                await ws.send(binary)
                assert await asyncio.wait_for(ws.recv(), 3) == binary
                await asyncio.wait_for(ws.wait_closed(), 3)
                assert ws.close_code == 1000
        asyncio.run(client())
    finally:
        server.should_exit = True
        thread.join(5)
        listener.close()
    assert not thread.is_alive()


@pytest.mark.parametrize('channels', [1, 2])
def test_pyav_live_filter_preserves_blocks_samples_and_gain(channels):
    from app.vst3_live_graph import Filter
    source = np.linspace(-.7, .7, 1057, dtype=np.float32).reshape(-1, 1)
    source = np.repeat(source, channels, axis=1)
    effect = Filter('volume=0.5', 48000, channels)
    result = []
    for start in range(0, len(source), 512):
        result.extend(effect.process(source[start:start+512]))
    result.extend(effect.flush())
    output = np.concatenate(result)
    assert output.shape == source.shape and output.dtype == np.float32
    np.testing.assert_allclose(output, source * .5, atol=1e-7)


@pytest.mark.parametrize('suffix', ['.txt', '.txt.gz'])
def test_smart_open_local_model_metadata_roundtrip(tmp_path, suffix):
    path = tmp_path / ('model' + suffix)
    metadata = {'instruments': ['voce — été', 'pianoforte'], 'sample_rate': 24000}
    with smart_open.open(path, 'w', encoding='utf-8') as out:
        json.dump(metadata, out, ensure_ascii=False)
    with smart_open.open(path, 'r', encoding='utf-8') as source:
        assert json.load(source) == metadata


@contextmanager
def model_http_server():
    content = bytes(range(256)) * 32
    state = {'etag': '"v1"', 'requests': []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            match = self.headers.get('If-Match')
            state['requests'].append(match)
            if match and match != state['etag']:
                self.send_response(412)
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            start = 0
            header = self.headers.get('Range')
            if header:
                start = int(header.split('=', 1)[1].split('-', 1)[0])
            body = content[start:]
            self.send_response(206 if header else 200)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('ETag', state['etag'])
            self.send_header('Accept-Ranges', 'bytes')
            if header:
                self.send_header('Content-Range', f'bytes {start}-{len(content)-1}/{len(content)}')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/model.bin', content, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


@pytest.mark.parametrize('changed', [False, True])
def test_smart_open_http_ranges_keep_original_resource_version(changed):
    import requests
    with model_http_server() as (url, content, state):
        with smart_open.open(url, 'rb', transport_params={'buffer_size': 8}) as source:
            assert source.read(3) == content[:3]
            if changed:
                state['etag'] = '"v2"'
                with pytest.raises(requests.HTTPError) as exc:
                    source.seek(4096, io.SEEK_SET)
                assert exc.value.response.status_code == 412
            else:
                source.seek(4096, io.SEEK_SET)
                assert source.read(13) == content[4096:4109]
            assert '"v1"' in state['requests']

