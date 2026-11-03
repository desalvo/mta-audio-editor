"""The five reviewed CI findings are narrowly scoped public non-secrets."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reviewed_fingerprints_are_exact_and_reference_recomputed_source_digests():
    review = json.loads((ROOT / 'docs/security/GITLEAKS_REVIEW_R210.json').read_text())
    case = review['shared_benchmark_false_positives_20261103']
    assert case['run_id'] == 41562792488 and case['finding_count'] == 5
    assert case['rule'] == 'generic-api-key'
    ignored = (ROOT / '.gitleaksignore').read_text().splitlines()
    occurrences = case['reviewed_occurrences']
    assert len(occurrences) == 5
    for item in occurrences:
        fingerprint = ':'.join([case['commit'], item['path'], case['rule'], str(item['line'])])
        assert ignored.count(fingerprint) == 1
    snapshot = json.loads((ROOT / 'docs/validation/r210/shared-benchmark/source-snapshot.json').read_text())
    for item in occurrences:
        if 'source' in item:
            source_hash = hashlib.sha256((ROOT / item['source']).read_bytes()).hexdigest()
            assert snapshot['app_source_sha256'][item['source']] == source_hash
        else:
            text = (ROOT / item['path']).read_text().splitlines()[item['line'] - 1]
            assert text.startswith('`tests/') and 'richieste API' in text


def test_exception_file_does_not_add_broad_suppression_for_these_findings():
    review = json.loads((ROOT / 'docs/security/GITLEAKS_REVIEW_R210.json').read_text())
    case = review['shared_benchmark_false_positives_20261103']
    entries = [line for line in (ROOT / '.gitleaksignore').read_text().splitlines()
               if line.startswith(case['commit'] + ':')]
    expected = {':'.join([case['commit'], item['path'], case['rule'], str(item['line'])])
                for item in case['reviewed_occurrences']}
    assert len(entries) == 5 and set(entries) == expected
