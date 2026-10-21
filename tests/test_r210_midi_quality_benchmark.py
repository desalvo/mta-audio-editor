from app.models import MidiNote
from app.music_interchange import MusicResult, MusicPart
from app.studio_midi_benchmark import evaluate, evaluate_files
import pytest


def score(parts):
    return MusicResult(parts=[MusicPart(id=f'p{i}',name=f'p{i}',program=program,percussion=drums,
         notes=[MidiNote(id=f'n{i}-{j}',pitch=pitch,start_ms=start,duration_ms=200)
                for j,(pitch,start) in enumerate(notes)])
                for i,(program,drums,notes) in enumerate(parts)])


def test_instrument_aware_note_matching():
    ref=score([(0,False,[(60,0),(62,500)]),(24,False,[(60,0)])])
    pred=score([(0,False,[(60,10),(62,508)]),(24,False,[(60,10)])])
    result=evaluate(ref,pred)
    assert result['f1']==1 and result['reference_instruments']==2
    wrong=score([(0,False,[(60,10),(62,508),(60,10)])])
    report=evaluate(ref,wrong)
    assert report['matched_notes']==2 and report['predicted_instruments']==1
    assert report['precision']==pytest.approx(2/3)
    assert report['recall']==pytest.approx(2/3)


def test_close_duplicate_predictions_match_only_once():
    ref=score([(0,False,[(60,100)])])
    pred=score([(0,False,[(60,95),(60,105)])])
    result=evaluate(ref,pred)
    assert result['matched_notes']==1 and result['precision']==0.5


def test_matching_is_maximum_cardinality_not_first_fit():
    ref=score([(0,False,[(60,100),(60,140)])])
    pred=score([(0,False,[(60,120),(60,100)])])
    result=evaluate(ref,pred,onset_ms=25)
    assert result['matched_notes']==2


def test_offset_matters_and_no_empty_fake_parts():
    ref=score([(0,False,[(60,0)])])
    pred=score([(0,False,[(60,90)])])
    assert evaluate(ref,pred)['matched_notes']==0
    with pytest.raises(ValueError):evaluate(ref,pred,onset_ms=-1)


def test_files_are_validated_and_bounded(tmp_path):
    ref=score([(0,False,[(60,0)])]);p=tmp_path/'ref.json';p.write_text(ref.model_dump_json())
    assert evaluate_files(p,p)['f1']==1
    bad=tmp_path/'invalid.json';bad.write_text('{}')
    with pytest.raises(Exception):evaluate_files(p,bad)
    link=tmp_path/'link.json';link.symlink_to(p)
    with pytest.raises(ValueError):evaluate_files(link,p)


def test_16_instrument_fixture_is_a_metric_not_a_claim_of_real_inference():
    items=[(i,False,[(60+i%12,100*i)]) for i in range(16)]
    result=evaluate(score(items),score(items))
    assert result['reference_instruments']==16 and result['f1']==1


def test_iterative_match_dense_chains_without_recursion():
    from app.studio_midi_benchmark import _match
    notes = [(60, float(i), float(i)+10) for i in range(1200)]
    assert _match(notes, notes, 0, 0) == 1200

def test_benchmark_event_limit():
    from app.studio_midi_benchmark import _match
    import pytest
    with pytest.raises(ValueError, match='20000'):
        _match([], [(60, 0, 10)] * 20001, 50, 100)


def test_benchmark_rejects_boolean_tolerances():
    valid = score([(0, False, [(60, 0)])])
    with pytest.raises(ValueError, match='tolerance'):
        evaluate(valid, valid, onset_ms=True)
    with pytest.raises(ValueError, match='tolerance'):
        evaluate(valid, valid, offset_ms=False)


def test_file_benchmark_fingerprints_exact_bytes(tmp_path):
    import hashlib
    reference = score([(0, False, [(60, 0)])])
    predicted = score([(0, False, [(60, 10)])])
    a, b = tmp_path/'reference.json', tmp_path/'prediction.json'
    a.write_bytes(reference.model_dump_json().encode())
    b.write_bytes(predicted.model_dump_json().encode())
    report = evaluate_files(a, b)
    assert report['input_provenance']['reference']['sha256'] == hashlib.sha256(a.read_bytes()).hexdigest()
    assert report['input_provenance']['prediction']['sha256'] == hashlib.sha256(b.read_bytes()).hexdigest()
    assert 'not certified' in report['input_provenance']['statement']
    b.write_bytes(b' ' + b.read_bytes())
    changed = evaluate_files(a, b)
    assert changed['input_provenance']['prediction']['sha256'] != report['input_provenance']['prediction']['sha256']
    assert changed['matched_notes'] == report['matched_notes']


def test_dense_benchmark_graph_is_bounded():
    from app.studio_midi_benchmark import _match
    notes = [(60, 0, 100)] * 1001
    with pytest.raises(ValueError, match="candidate pairs"):
        _match(notes, notes, 50, 100)


def test_benchmark_search_work_is_bounded(monkeypatch):
    """Bound augmenting searches even when the candidate graph is under its edge cap."""
    from app import studio_midi_benchmark as benchmark
    # A 500-note clique is below the graph-size cap but requires repeat scans.
    notes = [(60, 0, 100)] * 500
    assert benchmark._match(notes, notes, 50, 100) == 500
    # Above the cap the result must be an explicit failure, never partial metrics.
    huge = [(60, 0, 100)] * 1001
    with pytest.raises(ValueError, match='candidate pairs'):
        benchmark._match(huge, huge, 50, 100)


def test_benchmark_rejects_fifo_without_hanging(tmp_path):
    import os
    if not hasattr(os, 'mkfifo'):
        pytest.skip('FIFO unsupported')
    regular = tmp_path / 'regular.json'
    regular.write_text(score([(0, False, [(60, 0)])]).model_dump_json())
    fifo = tmp_path / 'untrusted_fifo.json'
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match='regular'):
        evaluate_files(fifo, regular)


def test_benchmark_rejects_directory(tmp_path):
    regular = tmp_path / 'regular.json'
    regular.write_text(score([(0, False, [(60, 0)])]).model_dump_json())
    with pytest.raises(ValueError, match='regular'):
        evaluate_files(tmp_path, regular)


def test_benchmark_rejects_file_mutation_during_read(tmp_path, monkeypatch):
    from app import studio_midi_benchmark as benchmark
    regular = tmp_path / 'regular.json'
    regular.write_text(score([(0, False, [(60, 0)])]).model_dump_json())
    original = benchmark.os.fstat
    counter = {'n': 0}
    def tampered_fstat(fd):
        stat_result = original(fd)
        counter['n'] += 1
        if counter['n'] == 2:
            class Changed:
                st_size = stat_result.st_size
                st_mtime_ns = stat_result.st_mtime_ns + 1
                st_ctime_ns = stat_result.st_ctime_ns
            return Changed()
        return stat_result
    monkeypatch.setattr(benchmark.os, 'fstat', tampered_fstat)
    with pytest.raises(ValueError, match='changed during reading'):
        benchmark.evaluate_files(regular, regular)


def test_quality_cli_rejects_invalid_instrument_target():
    from scripts.check_audio_midi_quality import main
    with pytest.raises(SystemExit) as error:
        main(['unused-reference','unused-prediction','--min-instruments','0'])
    assert error.value.code==2


@pytest.mark.parametrize('correct',[False,True])
def test_cli_instrument_target_cannot_be_met_with_spurious_parts(tmp_path,capsys,correct):
    import json
    from scripts.check_audio_midi_quality import main
    reference=score([(0,False,[(60,0)]),(24,False,[(64,0)])])
    prediction=reference if correct else score([(0,False,[(61,0)]),(24,False,[(65,0)])])
    ref=tmp_path/'reference.json';pred=tmp_path/'prediction.json'
    ref.write_text(reference.model_dump_json());pred.write_text(prediction.model_dump_json())
    assert main([str(ref),str(pred),'--min-instruments','2'])==(0 if correct else 2)
    report=json.loads(capsys.readouterr().out)
    assert report['predicted_instruments']==2
    assert report['correctly_matched_instruments']==(2 if correct else 0)
