"""Bounded offline lyric G2P in the operator's pinned DiffSinger interpreter.

This helper loads no acoustic weights, changes no admission policy and writes
no files. It closes the parent/runner dependency split on native/server installs.
"""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MAX_BYTES = 4 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--profile-sha256', required=True)
    parser.add_argument('--bank-sha256', required=True)
    options = parser.parse_args()
    from app.studio_offline_runner import activate
    activate()
    from app.vocal_phonemizer import load_profile, phonemize_score
    profile = load_profile(options.profile, options.profile_sha256, options.bank_sha256)
    raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('G2P request exceeds size budget')
    request = json.loads(raw)
    if (not isinstance(request, dict) or not isinstance(request.get('notes'), list)
            or not 1 <= len(request['notes']) <= 20000):
        raise ValueError('Invalid G2P score')
    encoded = json.dumps(phonemize_score(request, profile), ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > MAX_BYTES:
        raise ValueError('G2P response exceeds size budget')
    print(encoded)


if __name__ == '__main__':
    main()
