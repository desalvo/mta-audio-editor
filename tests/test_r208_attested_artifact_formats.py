"""Strict attested-result format checks, independent of the remote server."""
import io

import struct
import zipfile
import pytest
from app.ai_remote_client import _validate_attested_artifact, RemoteAIError


def wav(data=b''):
    return b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack('<IHHIIHH',16,1,1,8000,16000,2,16) + b'data' + struct.pack('<I',len(data)) + data


def archive(entries):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        for name,data in entries:
            z.writestr(name,data)
    return buf.getvalue()


@pytest.mark.parametrize('payload,mime', [
    (b'', 'audio/wav'), (b'RIFF', 'audio/wav'), (b'WAVE' + wav()[4:], 'audio/wav'),
    (wav()[:8] + b'NOTW' + wav()[12:], 'audio/wav'),
    (wav()[:4] + b'\x00\x00\x00\x00' + wav()[8:], 'audio/wav'),
    (wav() + b'extra', 'audio/wav'),
    (b'', 'application/json'), (b'{', 'application/json'),
    (b'null', 'application/json'), (b'123', 'application/json'),
    (b'"test"', 'application/json'), (b'{"a":1,"a":2}', 'application/json'),
    (b'{"a":{"b":1,"b":2}}', 'application/json'),
    (b'{"n":NaN}', 'application/json'), (b'{"n":Infinity}', 'application/json'),
    (b'\xff', 'application/json'),
    (b'not a zip', 'application/zip'),
    (archive([]), 'application/zip'),
    (archive([('../outside',b'bad')]), 'application/zip'),
    (archive([('/root',b'bad')]), 'application/zip'),
    (archive([('dir/../outside',b'bad')]), 'application/zip'),
    (archive([('dir\\evil',b'bad')]), 'application/zip'),
    (archive([('dir//file',b'bad')]), 'application/zip'),
    (archive([('item',b'x'),('item',b'y')]), 'application/zip'),
])
def test_reject_invalid_attested_result(payload,mime):
    with pytest.raises(RemoteAIError):
        _validate_attested_artifact(payload,mime)


@pytest.mark.parametrize('payload,mime', [
    (wav(), 'audio/wav'), (wav(b'\x00\x00'), 'audio/wav'),
    (b'{}','application/json'), (b'[]','application/json'),
    (b'{"items":[1,true,null]}','application/json'),
    (archive([('stem.wav',wav())]), 'application/zip'),
])
def test_allow_valid_attested_result(payload,mime):
    _validate_attested_artifact(payload,mime)
