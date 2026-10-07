from pathlib import Path
import json
import subprocess
import zipfile

from app.models import Chord, LyricLine, Project, ProjectExportRequest, Track
from app.mp3g import build_mp3g_zip
from app.audio_engine import render_mix


def _tone(path: Path, rate: int = 44100):
    subprocess.run([
        'ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.7',
        '-ar',str(rate),'-ac','2',str(path)
    ], check=True)


def _rate(path: Path) -> int:
    out = subprocess.check_output([
        'ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=sample_rate',
        '-of','default=nw=1:nk=1',str(path)
    ], text=True).strip()
    return int(out)


def test_models_accept_project_and_export_96k():
    assert Project(id='a'*12,title='x',sample_rate=96000).sample_rate == 96000
    req = ProjectExportRequest(format='wav', sample_rate=96000, wav_bit_depth=32)
    assert req.sample_rate == 96000 and req.wav_bit_depth == 32
    assert ProjectExportRequest(format='mp3g').format == 'mp3g'


def test_wav_export_24_and_32_at_96k(tmp_path: Path):
    source = tmp_path/'source.wav'; _tone(source, 48000)
    p = Project(id='a'*12,title='x',sample_rate=48000,tracks=[Track(id='t1',name='t',filename='source.wav',duration_ms=700,sample_rate=48000)])
    p.tracks[0].clips=[]
    for bits, codec in [(24,'pcm_s24le'),(32,'pcm_f32le')]:
        out=tmp_path/f'out-{bits}.wav'
        render_mix(p, lambda _pid,_fn: source, out, fmt='wav', sample_rate=96000, wav_bit_depth=bits)
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(out)],text=True))['streams'][0]
        assert int(info['sample_rate']) == 96000
        assert info['codec_name'] == codec


def test_mp3g_zip_has_matching_mp3_and_cdg(tmp_path: Path):
    mp3=tmp_path/'song.mp3'; _tone(mp3,44100)
    p=Project(id='b'*12,title='Song',artist='Artist',lyrics=[LyricLine(time_ms=0,text='Hello world')],chords=[Chord(time_ms=0,chord='C')])
    out=tmp_path/'song.zip'
    build_mp3g_zip(p,mp3,out,'Song',700)
    with zipfile.ZipFile(out) as z:
        assert sorted(z.namelist()) == ['Song.cdg','Song.mp3']
        cdg=z.read('Song.cdg')
        assert len(cdg) % 24 == 0 and len(cdg) >= 300*24//2
        assert z.read('Song.mp3')[:3] in {b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'}

def test_import_rate_conversion_96_to_project_48(tmp_path, monkeypatch):
    from app import main
    source = tmp_path/'upload.wav'; _tone(source,96000)
    monkeypatch.setattr(main, 'audio_path', lambda _pid, name: tmp_path/name)
    name, converted, source_rate = main._normalize_audio_to_project_rate('x', 'upload.wav', 48000)
    assert source_rate == 96000
    assert name.endswith('-sr48000.wav') and converted.is_file()
    assert _rate(converted) == 48000
    assert not source.exists()


def test_project_rate_change_is_locked_with_tracks(monkeypatch):
    from app import main
    current=Project(id='c'*12,title='x',sample_rate=44100,tracks=[Track(id='t1',name='t',filename='x.wav',duration_ms=100)])
    changed=current.model_copy(deep=True); changed.sample_rate=48000
    monkeypatch.setattr(main,'_project_for_actor',lambda *_a,**_k:current)
    try:
        main.project_put(current.id,changed,None)
    except Exception as exc:
        assert getattr(exc,'status_code',None)==409
    else:
        raise AssertionError('sample rate change should be rejected while tracks exist')


def test_clip_library_instantiation_converts_to_current_project_rate(tmp_path, monkeypatch):
    import wave
    from fastapi.testclient import TestClient
    import app.main as main
    import app.storage as storage
    from app.models import ProjectClip

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Clip rate", sample_rate=48000)
    src = storage.pdir(project.id) / "audio" / "library-96.wav"
    with wave.open(str(src), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(96000)
        handle.writeframes(b"\\x00\\x00" * 9600)
    asset = ProjectClip(id="asset96", name="96k clip", filename=src.name, duration_ms=100, sample_rate=96000)
    project.clip_library = [asset]
    storage.save_project(project)
    client = TestClient(main.app, headers={"X-MTA-Request":"1"})
    response = client.post(f"/api/projects/{project.id}/clip-library/{asset.id}/instantiate", json={"timeline_start_ms":0})
    assert response.status_code == 200, response.text
    payload = response.json()
    track = payload["track"]
    assert track["sample_rate"] == 48000
    assert track["filename"] != asset.filename
    derived = storage.pdir(project.id) / "audio" / track["filename"]
    assert main._audio_sample_rate(derived) == 48000
    assert main._audio_sample_rate(src) == 96000
