"""External-library contracts behind the reviewed h5py/beartype updates."""
from pathlib import Path
from typing import Callable

from beartype import beartype
from beartype.door import is_bearable
from beartype.roar import BeartypeCallHintParamViolation
import h5py
import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('value,accepted', [(None, True), (lambda: 7, True), (42, False), ('callback', False)])
def test_roformer_callable_union_is_checked_and_enforced(value, accepted):
    @beartype
    def optional_callback(callback: Callable | None):
        return callback
    assert is_bearable(value, Callable | None) is accepted
    if accepted:
        assert optional_callback(value) is value
    else:
        with pytest.raises(BeartypeCallHintParamViolation):
            optional_callback(value)


def test_hdf5_weight_arrays_and_metadata_roundtrip(tmp_path):
    weights = np.arange(30, dtype=np.float32).reshape(5, 6) / 7
    path = tmp_path / 'weights.h5'
    with h5py.File(path, 'w') as archive:
        archive.create_dataset('network/weights', data=weights, compression='gzip')
        archive.attrs['instrument'] = 'voce — français'
    with h5py.File(path, 'r') as archive:
        restored = archive['network/weights'][()]
        assert restored.dtype == weights.dtype
        np.testing.assert_array_equal(restored, weights)
        assert archive.attrs['instrument'] == 'voce — français'


def test_dependabot_preserves_historical_evidence_and_runtime_families():
    from fnmatch import fnmatchcase
    config = yaml.safe_load((ROOT / '.github/dependabot.yml').read_text())
    pip = next(item for item in config['updates'] if item['package-ecosystem'] == 'pip')
    excluded = pip['exclude-paths']
    for name in ['validation/r210-acceptance-conversion-freeze.txt',
                 'validation/r210-qixuan-itfr-environment.txt',
                 'docs/validation/r210/runtime/requirements.txt',
                 'native/third_party/model/requirements.txt']:
        assert any(fnmatchcase(name, pattern) for pattern in excluded), name
    assert not any(fnmatchcase('requirements.txt', pattern) for pattern in excluded)
    rules = {item['dependency-name']: item for item in pip['ignore']}
    assert {'torch', 'torchaudio', 'torchvision'} <= rules.keys()
    for name in ['numba', 'llvmlite', 'scipy', 'contourpy']:
        assert set(rules[name]['update-types']) == {'version-update:semver-major', 'version-update:semver-minor'}
    docker = next(item for item in config['updates'] if item['package-ecosystem'] == 'docker')
    rule = next(item for item in docker['ignore'] if item['dependency-name'] == 'python')
    assert set(rule['update-types']) == {'version-update:semver-major', 'version-update:semver-minor'}
