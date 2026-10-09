"""Multi-singer SAM temporal references, routing and persisted UI controls."""
import json
from pathlib import Path
import pytest
from app import main


SINGERS = [
    {"name": "Voce A", "start": 12, "end": 16},
    {"name": "Voce B", "start": 29.5, "end": 34.5},
    {"name": "Voce C", "start": 46, "end": 52},
]


def test_multi_singer_validated_and_selective():
    parsed, selected = main._parse_singers_json(json.dumps(SINGERS), "sam-audio-small", "singer_2")
    assert selected == "singer_2"
    assert [s["id"] for s in parsed] == ["singer_1", "singer_2", "singer_3"]
    assert [s["name"] for s in parsed] == ["Voce A", "Voce B", "Voce C"]
    assert main._parse_singers_json(json.dumps(SINGERS[:2]), "sam-audio-base")[1] == "all"


@pytest.mark.parametrize("value,model,target,match", [
    ('!', 'sam-audio-small', 'all', 'JSON'),
    ('[]', 'sam-audio-small', 'all', '2 to 8'),
    (json.dumps(SINGERS), 'invalid-model', 'all', 'model'),
    (json.dumps(SINGERS), 'sam-audio-small', 'singer_4', 'not defined'),
    (json.dumps([SINGERS[0], SINGERS[0]]), 'sam-audio-small', 'all', 'unique'),
    (json.dumps([SINGERS[0], {'name': 'Z', 'start': 13, 'end': 15}]), 'sam-audio-small', 'all', 'overlap'),
    (json.dumps([SINGERS[0], {'name': 'Z', 'start': 20, 'end': 20.1}]), 'sam-audio-small', 'all', '0.5-60'),
    (json.dumps([SINGERS[0], {'name': 'Z', 'start': 'oops', 'end': 30}]), 'sam-audio-small', 'all', 'numeric'),
    (json.dumps([SINGERS[0], 7]), 'sam-audio-small', 'all', 'reference'),
    (json.dumps([SINGERS[0], {'name': 'Z', 'start': float('nan'), 'end': 20}]), 'sam-audio-small', 'all', '0.5-60'),
])
def test_invalid_singer_references(value, model, target, match):
    with pytest.raises(ValueError, match=match):
        main._parse_singers_json(value, model, target)


def test_sam_temporal_anchors_separate_every_or_one_singer(tmp_path, monkeypatch):
    parsed, _ = main._parse_singers_json(json.dumps(SINGERS), 'sam-audio-large')
    seen = []
    def fake_infer(source, directory, model, target, anchors=None):
        seen.append((Path(source), model, target, anchors))
        directory.mkdir(parents=True, exist_ok=True)
        result = directory / f'{target}.wav'
        result.write_bytes(b'RIFF' + b'0'*90)
        return result
    monkeypatch.setattr(main, '_sam_audio_extract', fake_infer)
    source = tmp_path / 'vocals.wav'
    all_outputs = main._extract_singer_stems(source, tmp_path / 'all', 'sam-audio-large', parsed)
    assert [p.name for p in all_outputs] == ['singer_1.wav', 'singer_2.wav', 'singer_3.wav']
    assert seen[1][3] == [['+', 29.5, 34.5], ['-', 12.0, 16.0], ['-', 46.0, 52.0]]
    seen.clear()
    selected = main._extract_singer_stems(source, tmp_path / 'single', 'sam-audio-small', parsed, 'singer_3')
    assert [p.name for p in selected] == ['singer_3.wav']
    assert len(seen) == 1 and seen[0][3][0] == ['+', 46.0, 52.0]


def test_multi_singer_ui_and_sam_worker_contract():
    js = Path('app/static/app.js').read_text()
    worker = Path('app/sam_audio_worker.py').read_text()
    for token in ('trackSingerEnabled','stemSingerEnabled','collectSingerSelection', 'singers_json=',
                  'singerTimeToSeconds', 'syncSingerTargets', 'mta.singer.model'):
        assert token in js
    assert '--anchors-json' in worker
    assert '"anchors"' in worker
    assert 'singers_json: str = ""' in Path('app/main.py').read_text()


def test_multi_singer_job_keeps_synchronized_tracks_and_selective_replacement(tmp_path, monkeypatch):
    """Run the production job path with Demucs/SAM mocked, not the timeline/storage."""
    import threading
    import time
    from app.models import Project, Track, Clip
    project = Project(id='singertest', title='Duet test', tracks=[
        Track(id='original', name='Original Mix', type='other', filename='original.wav',
              duration_ms=150000, clips=[Clip(id='originalclip', source_start_ms=0,
                                              source_end_ms=150000, timeline_start_ms=0)])
    ])
    monkeypatch.setattr(main, 'load_project', lambda pid: project)
    monkeypatch.setattr(main, 'save_project', lambda current: None)
    monkeypatch.setattr(main, 'audio_path', lambda pid, name: tmp_path / name)
    monkeypatch.setattr(main, 'ffprobe', lambda src: {'duration':150.0})
    monkeypatch.setattr(main, 'media_duration_ms', lambda dst: 150000)
    monkeypatch.setattr(main, '_audio_channel_info', lambda dst: (2,'stereo'))
    monkeypatch.setattr(main, '_normalize_audio_to_project_rate', lambda pid, name, rate, strict=False:(name,tmp_path/name,False))
    def fake_demucs(src, output, **kwargs):
        output.mkdir(parents=True, exist_ok=True)
        results=[]
        for name in ('vocals', 'bass'):
            path=output/f'{name}.wav';path.write_bytes(b'RIFF'+b'0'*100);results.append(path)
        return results
    monkeypatch.setattr(main.STEM_SPLITTER, 'split', fake_demucs)
    chosen=[]
    def fake_singers(src, output, model, specs, selected):
        chosen.append((src.name,model,selected))
        output.mkdir(parents=True, exist_ok=True)
        paths=[]
        for singer in specs:
            if selected=='all' or selected==singer['id']:
                path=output/f"{singer['id']}.wav";path.write_bytes(b'RIFF'+b'0'*100);paths.append(path)
        return paths
    monkeypatch.setattr(main, '_extract_singer_stems', fake_singers)
    singers, _ = main._parse_singers_json(json.dumps(SINGERS), 'sam-audio-small')
    def start(target):
        job_id='r276'+target
        main.STEM_JOBS[job_id]={
            'id':job_id,'project_id':project.id,'status':'queued','progress':1,
            'message':'queued','created_at':time.time(),'updated_at':time.time(),
            'cancel_event':threading.Event(),'model':'htdemucs','stem_count':4,
            'filename':'original.wav','source_track_id':'original','stem_targets':['all'],
            'singer_mode':True,'singers':singers,'singer_target':target,
            'singer_model':'sam-audio-small','estimate_bpm':False,
        }
        input_file=tmp_path/'original.wav';input_file.write_bytes(b'RIFF'+b'0'*100)
        main._stem_split_worker(job_id,input_file,True)
        job=main.STEM_JOBS.pop(job_id)
        assert job['status']=='completed',job.get('error')
    start('all')
    assert chosen==[('vocals.wav','sam-audio-small','all')]
    assert {'Voce A','Voce B','Voce C','Bass'} <= {track.name for track in project.tracks}
    singer_tracks=[track for track in project.tracks if track.name.startswith('Voce ')]
    assert len(singer_tracks)==3
    assert {track.clips[0].timeline_start_ms for track in singer_tracks}=={0}
    assert {track.duration_ms for track in singer_tracks}=={150000}
    before={track.name:track.id for track in singer_tracks}
    start('singer_2')
    after={track.name:track.id for track in project.tracks if track.name.startswith('Voce ')}
    assert before==after   # Existing Singer B stem was replaced rather than duplicated
