from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('preflight', ROOT / 'scripts/repositories/preflight_package_copy.py')
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def create(src, dest, count=2):
    for sub, extension in (('', '.deb'), ('rpm/el9', '.rpm'), ('rpm/el10', '.rpm')):
        folder = src / sub
        folder.mkdir(parents=True, exist_ok=True)
        for n in range(count):
            (folder / f'new{n}{extension}').write_bytes(b'new')
    for sub, extension in (('apt/early/pool', '.deb'), ('rpm/early/el9/packages', '.rpm'), ('rpm/early/el10/packages', '.rpm')):
        folder = dest / sub
        folder.mkdir(parents=True, exist_ok=True)
        for n in range(3):
            (folder / f'old{n}{extension}').write_bytes(b'old')


def test_pre_copy_prunes_each_os(tmp_path):
    source, target = tmp_path / 'incoming', tmp_path / 'staging'
    create(source, target)
    mod.prepare(source, target, 'early')
    for sub, extension in (('apt/early/pool', '.deb'), ('rpm/early/el9/packages', '.rpm'), ('rpm/early/el10/packages', '.rpm')):
        assert not list((target / sub).glob('*' + extension))


def test_rejects_more_than_twenty_before_mutating_destination(tmp_path):
    source, target = tmp_path / 'incoming', tmp_path / 'staging'
    create(source, target, 21)
    with pytest.raises(ValueError, match='between 1 and 20'):
        mod.prepare(source, target, 'early')
    assert (target / 'apt/early/pool/old0.deb').exists()


def test_cleanup_run_before_package_copy():
    script = (ROOT / 'scripts/repositories/build_indexes.sh').read_text()
    assert script.index('preflight_package_copy.py') < script.index('cp -n "$f"')


def test_accepts_twenty_retained_builds_per_pool(tmp_path):
    source, target = tmp_path / 'incoming', tmp_path / 'staging'
    create(source, target, 20)
    mod.prepare(source, target, 'early')
    for sub, extension in (('apt/early/pool', '.deb'), ('rpm/early/el9/packages', '.rpm'), ('rpm/early/el10/packages', '.rpm')):
        assert not list((target / sub).glob('*' + extension))


def test_rejects_invalid_preflight_retention_limit(tmp_path):
    source, target = tmp_path / 'incoming', tmp_path / 'staging'
    create(source, target)
    with pytest.raises(ValueError, match='Invalid channel or retention limit'):
        mod.prepare(source, target, 'early', limit=0)
    with pytest.raises(ValueError, match='Invalid channel or retention limit'):
        mod.prepare(source, target, 'early', limit=101)
