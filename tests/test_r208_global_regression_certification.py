import json

from scripts.verify_global_regression import verify


def _report(folder, number, total=2, **changes):
    item = {'shard': number, 'shards': total, 'exit_code': 0, 'timed_out': False,
            'junit': f'shard-{number}.xml', 'counts': {'tests': 5, 'failures': 0, 'errors': 0, 'skipped': 0}}
    item.update(changes)
    target = folder / f'shard-{number:02d}-of-{total:02d}.json'
    target.write_text(json.dumps(item))


def test_all_reports_required(tmp_path):
    _report(tmp_path, 0)
    assert not verify(tmp_path, 2)['passed']
    _report(tmp_path, 1)
    result = verify(tmp_path, 2)
    assert result['passed'] and result['tests'] == 10


def test_failed_or_corrupt_report_rejected(tmp_path):
    _report(tmp_path, 0)
    _report(tmp_path, 1, exit_code=124, timed_out=True)
    assert not verify(tmp_path, 2)['passed']
    _report(tmp_path, 1, counts={'tests': 5, 'failures': 1, 'errors': 0})
    assert not verify(tmp_path, 2)['passed']
    (tmp_path / 'shard-01-of-02.json').write_text('{bad')
    assert not verify(tmp_path, 2)['passed']


def test_duplicate_report_rejected(tmp_path):
    _report(tmp_path, 0)
    _report(tmp_path, 1)
    sub = tmp_path / 'duplicate'
    sub.mkdir()
    _report(sub, 1)
    assert not verify(tmp_path, 2)['passed']
