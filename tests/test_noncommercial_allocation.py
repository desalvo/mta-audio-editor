"""Non-commercial allocation must never invent revenue or bypass integer safeguards."""
import pytest

from app.noncommercial_allocation import allocate_period, remaining_recoverable_cents


def test_full_recovery_is_never_exceeded():
    assert allocate_period(100, {'a': 1, 'b': 1, 'c': 1}) == {'a': 34, 'b': 33, 'c': 33}
    assert allocate_period(7, {'b': 0, 'a': 3}) == {'a': 7, 'b': 0}
    assert allocate_period(7, {'a': 0, 'b': 0}) == {'a': 0, 'b': 0}


def test_allocation_conserves_cost_for_positive_usage():
    for amount in range(0, 100):
        shares = allocate_period(amount, {'a': 1, 'b': 5, 'c': 11})
        assert sum(shares.values()) == amount


@pytest.mark.parametrize('amount,usage', [(-1, {'a': 1}), (True, {'a': 1}),
                                            (10, {'a': -2}), (10, {'a': 1.2}),
                                            (10, {'a': True}), (10, {'': 1})])
def test_reject_malformed_cost_or_usage(amount, usage):
    with pytest.raises(ValueError):
        allocate_period(amount, usage)


def test_remaining_recovery_caps_contributions():
    assert remaining_recoverable_cents(100, 63) == 37
    with pytest.raises(ValueError):
        remaining_recoverable_cents(100, 101)
