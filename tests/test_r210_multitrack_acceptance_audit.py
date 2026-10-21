import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_multitrack_acceptance import audit


def report(programs=10):
    return {
        'protocol': 'fixed-zero-offset-50ms-onset-100ms-offset',
        'models': {'model': {'overall': {'f1': 0.91}, 'per_program': {
            str(i): {'matched': 1, 'reference_notes': 1, 'predicted_notes': 1}
            for i in range(programs)
        }}},
    }


def test_instrument_count_is_not_quality_certification():
    result = audit(report(16))
    assert result['models']['model']['matched_melodic_programs'] == 16
    assert result['models']['model']['minimum_instrument_evidence']
    assert not result['accuracy_10_to_16_certified']
    assert not result['models']['model']['quality_certified']


def test_insufficient_instrument_evidence():
    assert not audit(report(9))['models']['model']['minimum_instrument_evidence']


def test_drum_excluded_from_melodic_count():
    r = report(9)
    r['models']['model']['per_program']['drums'] = {'matched': 100, 'reference_notes': 100, 'predicted_notes': 100}
    assert audit(r)['models']['model']['matched_melodic_programs'] == 9


@pytest.mark.parametrize('change', [
    lambda r: r.update(protocol='offset-fitted'),
    lambda r: r['models']['model']['per_program']['0'].update(matched=2),
    lambda r: r['models']['model']['overall'].update(f1=1.2),
])
def test_invalid_evidence_rejected(change):
    r = report()
    change(r)
    with pytest.raises(ValueError):
        audit(r)


def test_bad_range_rejected():
    with pytest.raises(ValueError):
        audit(report(), minimum=16, maximum=10)
