"""Independent lyrics for vocal parts with different note counts."""
import pytest
from app.vocal_synthesis import Settings


def test_independent_singer_lyrics_settings():
    settings=Settings.model_validate({'language':'en','voice_syllables':[['hello','world'],['ah']]})
    assert settings.voice_syllables==[['hello','world'],['ah']]
    assert Settings.model_validate({'language':'en','syllables':['old']}).voice_syllables==[]


@pytest.mark.parametrize('payload', [
    {'voice_syllables':[['']]},
    {'voice_syllables':[['a'*501]]},
    {'voice_syllables':[[]]*9},
])
def test_invalid_singer_lyrics_refused(payload):
    with pytest.raises(ValueError):
        Settings.model_validate(payload)


def test_per_singer_alignment_handles_different_melody_lengths():
    from types import SimpleNamespace
    from app.vocal_synthesis import validate_voice_lyrics
    parts=[SimpleNamespace(notes=[SimpleNamespace(start_ms=i*1000,duration_ms=500,pitch=60) for i in range(3)]),SimpleNamespace(notes=[SimpleNamespace(start_ms=0,duration_ms=500,pitch=64)])]
    validate_voice_lyrics(parts,Settings(language='en',voice_syllables=[['a','b','c'],['d']]))
    with pytest.raises(ValueError,match='one independent'):
        validate_voice_lyrics(parts,Settings(language='en',voice_syllables=[['a']]))
    with pytest.raises(ValueError,match='one English syllable'):
        validate_voice_lyrics(parts,Settings(language='en',voice_syllables=[['a','b'],['d']]))


def test_lyrics_follow_notes_when_input_order_differs_from_timeline():
    from types import SimpleNamespace
    from app.vocal_synthesis import ordered_voice_events, validate_voice_lyrics
    note_late=SimpleNamespace(start_ms=2000,duration_ms=500,pitch=64)
    note_early=SimpleNamespace(start_ms=0,duration_ms=500,pitch=60)
    part=SimpleNamespace(notes=[note_late,note_early])
    cfg=Settings(language='en',syllables=['later','first'])
    validate_voice_lyrics([part],cfg)
    assert ordered_voice_events(part,cfg.syllables)==[(note_early,'first'),(note_late,'later')]


def test_invalid_overlap_and_overlong_part_refused_before_voicebank_loading():
    from types import SimpleNamespace
    from app.vocal_synthesis import validate_voice_lyrics
    def note(start,duration):
        return SimpleNamespace(start_ms=start,duration_ms=duration,pitch=60)
    for notes,match in [([note(0,600),note(500,500)],'monophonic'),
                        ([note(599500,1000)],'ten minutes'),([], 'melody')]:
        with pytest.raises(ValueError,match=match):
            validate_voice_lyrics([SimpleNamespace(notes=notes)],Settings())


@pytest.mark.parametrize('patch', [
    {'start_ms': -1}, {'duration_ms': 0}, {'duration_ms': 30001},
    {'pitch': 128}, {'velocity': -1}, {'start_ms': float('nan')},
])
def test_invalid_vocal_notes_rejected_before_loading_bank(patch):
    from types import SimpleNamespace
    from app.vocal_synthesis import validate_voice_lyrics
    base=dict(start_ms=0, duration_ms=500, pitch=60, velocity=96)
    base.update(patch)
    with pytest.raises(ValueError, match='Invalid vocal note'):
        validate_voice_lyrics([SimpleNamespace(notes=[SimpleNamespace(**base)])], Settings())


def test_independent_generation_metadata_survives_audio_midi_publication_and_reopen(tmp_path,monkeypatch):
    """Synthetic test PCM exercises real publication/persistence, not inference."""
    import io,uuid
    import numpy as np
    import soundfile as sf
    from app import main,storage,auth
    from app.models import MidiNote
    from app.music_interchange import MusicResult,MusicPart
    from app.music_publication import revision
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    monkeypatch.setattr(auth,'data_root',lambda:tmp_path/'account')
    monkeypatch.setattr(main,'_ensure_workspace_capacity',lambda *args,**kwargs:None)
    project=storage.create_project('Vocal metadata',target='DAW_MIDI')
    parts=[MusicPart(id=f'source-{i}-melody',name=f'Singer {i}',notes=[MidiNote(id='n',pitch=60+i,start_ms=0,duration_ms=500)],source_model='contract-test') for i in range(2)]
    result=MusicResult(parts=parts,offset_ms=1000)
    buffer=io.BytesIO();sf.write(buffer,np.sin(np.arange(24000)*2*np.pi*440/48000)*.1,48000,format='WAV',subtype='PCM_24')
    generation={'schema':'mta-multi-singer-generation-1','backend':'diffsinger',
        'part_sources':{parts[0].id:'track-it',parts[1].id:'track-fr'},
        'sources':{'track-it':{'backend':'diffsinger','settings':{'language':'it','syllables':['la']}},
                   'track-fr':{'backend':'diffsinger','settings':{'language':'fr','syllables':['bon']}}}}
    main._midi_music_publish(project,uuid.uuid4().hex,revision(project),result,
                            audio={p.id:buffer.getvalue() for p in parts},generation=generation)
    saved=storage.load_project(project.id)
    assert len(saved.tracks)==4
    for track in saved.tracks:
        language='it' if track.music_part_id==parts[0].id else 'fr'
        assert track.music_generation['settings']['language']==language
        assert 'sources' not in track.music_generation
        if track.kind=='audio':
            assert track.clips[0].timeline_start_ms==1000
            assert track.music_source_model=='contract-test'
            assert storage.audio_path(saved.id,track.filename).is_file()
