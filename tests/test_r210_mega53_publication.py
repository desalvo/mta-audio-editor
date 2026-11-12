"""Real filesystem/PCM publication; model execution is an explicit synthetic fixture."""
from pathlib import Path
from threading import Event
import wave

import pytest

from app import mega53_runtime as runtime, model_license_policy, separator_process


@pytest.fixture(params=['vocals', 'drums', 'remote'])
def operation(request, tmp_path, monkeypatch):
    event = Event()
    root = tmp_path / 'upstream'
    root.mkdir()
    (root / 'inference.py').write_text('# synthetic output producer, no model')
    config, checkpoint, source = [tmp_path / n for n in ['model.yaml', 'weights.ckpt', 'input.wav']]
    config.write_text('synthetic')
    checkpoint.write_bytes(b'synthetic')
    with wave.open(str(source), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(44100)
        wav.writeframes(bytes(3200))
    audio = source.read_bytes()
    import sys
    for name, value in [('ROOT', root), ('CONFIG', config), ('CHECKPOINT', checkpoint),
                        ('PYTHON', Path(sys.executable).resolve())]:
        monkeypatch.setenv('MTA_MEGA53_' + name, str(value))
    monkeypatch.setattr(runtime, 'verify_mega53_checkpoint', lambda p: Path(p))
    monkeypatch.setattr(model_license_policy, 'evaluate_model', lambda _: None)
    def run(command, **kwargs):
        output = Path(command[command.index('--store_dir') + 1])
        for name in ['lead-vocal', 'back-vocal', 'drums', 'percussion']:
            (output / (name + '.wav')).write_bytes(audio)
    monkeypatch.setattr(separator_process, 'run', run)
    out = tmp_path / 'published'
    names = (['lead_vocals.wav', 'backing_vocals.wav'] if request.param == 'vocals'
             else ['drums_without_percussions.wav', 'percussions.wav'])
    def invoke():
        if request.param == 'vocals':
            return runtime.infer(source, out, cancel_event=event)[:2]
        if request.param == 'drums':
            return runtime.infer_drums(source, out, {'drums', 'percussion'}, cancel_event=event)
        result, job = runtime.dispatch_drums(source, out, {'drums', 'percussion'}, cancel_event=event,
            remote=lambda *a: ({'audio': {n: audio for n in names}}, 'original-worker-job'))
        assert job == 'original-worker-job'
        return result
    return invoke, out, names, event, request.param, audio


def test_complete_group_is_published_with_exact_audio(operation):
    invoke, out, names, _, _, audio = operation
    result = invoke()
    assert list(result) == [out / n for n in names]
    assert {p.name for p in out.iterdir()} == set(names)
    assert all(p.read_bytes() == audio for p in result)


@pytest.mark.parametrize('symlink', [False, True])
def test_collision_on_second_output_preserves_original_and_removes_first(operation, tmp_path, symlink):
    invoke, out, names, _, _, _ = operation
    out.mkdir()
    victim = out / names[1]
    if symlink:
        original = tmp_path / 'foreign.wav'; original.write_bytes(b'foreign audio')
        victim.symlink_to(original)
    else:
        victim.write_bytes(b'foreign audio')
    with pytest.raises(FileExistsError):
        invoke()
    assert victim.read_bytes() == b'foreign audio'
    assert victim.is_symlink() == symlink
    assert {p.name for p in out.iterdir()} == {names[1]}


@pytest.mark.parametrize('when', [1, 2])
def test_cancellation_during_publication_rolls_back_whole_group(operation, monkeypatch, when):
    invoke, out, _, event, _, _ = operation
    original = runtime.os.link
    count = 0
    def link(source, target):
        nonlocal count
        original(source, target)
        count += 1
        if count == when: event.set()
    monkeypatch.setattr(runtime.os, 'link', link)
    with pytest.raises(RuntimeError, match='cancelled'):
        invoke()
    assert not list(out.iterdir())


def test_publication_io_failure_rolls_back_whole_group(operation, monkeypatch):
    invoke, out, _, _, _, _ = operation
    original = runtime.os.link
    count = 0
    def link(source, target):
        nonlocal count
        count += 1
        if count == 2: raise OSError('disk full')
        return original(source, target)
    monkeypatch.setattr(runtime.os, 'link', link)
    with pytest.raises(OSError, match='disk full'):
        invoke()
    assert not list(out.iterdir())


def test_rollback_preserves_output_replaced_by_another_writer(operation, monkeypatch):
    invoke, out, names, _, _, _ = operation
    original = runtime.os.link
    count = 0
    def link(source, target):
        nonlocal count
        count += 1
        if count == 2:
            first = out / names[0]
            first.unlink(); first.write_bytes(b'concurrent replacement')
            raise OSError('later publication failed')
        return original(source, target)
    monkeypatch.setattr(runtime.os, 'link', link)
    with pytest.raises(OSError, match='later publication failed'):
        invoke()
    assert {p.name for p in out.iterdir()} == {names[0]}
    assert (out / names[0]).read_bytes() == b'concurrent replacement'


def test_local_policy_revocation_after_final_link_removes_outputs(operation, monkeypatch):
    invoke, out, _, _, mode, _ = operation
    if mode == 'remote':
        # Remote policy belongs to the executing worker, not this publisher.
        monkeypatch.setattr(model_license_policy, 'evaluate_model', lambda _: pytest.fail('Local policy used for remote output'))
        assert len(invoke()) == 2
        return
    original = runtime.os.link
    count = 0
    revoked = False
    def policy(_):
        if revoked: raise RuntimeError('rights revoked')
    monkeypatch.setattr(model_license_policy, 'evaluate_model', policy)
    def link(source, target):
        nonlocal count, revoked
        original(source, target)
        count += 1
        if count == 2: revoked = True
    monkeypatch.setattr(runtime.os, 'link', link)
    with pytest.raises(RuntimeError, match='rights revoked'):
        invoke()
    assert not list(out.iterdir())
