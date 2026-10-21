from scripts.evaluate_mrmt3_alignment import match


def test_alignment_zero_and_shift():
    ref = [(4, 60, 1.10, 1.40)]
    pred = [(4, 60, 1.00, 1.30)]
    assert match(ref, pred) == 0
    assert match(ref, pred, shift=0.10) == 1


def test_strict_program_match_and_diagnostic():
    ref = [(4, 60, 1.00, 1.30)]
    pred = [(8, 60, 1.00, 1.30)]
    assert match(ref, pred) == 0
    assert match(ref, pred, program_agnostic=True) == 1


def test_one_to_one_matching():
    ref = [(4, 60, 1.00, 1.30)]
    pred = [(4, 60, 1.00, 1.30), (4, 60, 1.00, 1.30)]
    assert match(ref, pred) == 1
