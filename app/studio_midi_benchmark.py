"""Offline, instrument-aware Audio-to-MIDI benchmark using reviewed MusicResult JSON.

No ML model downloads, synthetic ground truth or fake accuracy claims.
"""
from collections import defaultdict
from bisect import bisect_left, bisect_right
import math
from pathlib import Path
import hashlib
import os
import stat

from .music_interchange import MusicResult, parse_result


def _events(score):
    grouped = defaultdict(list)
    event_count = 0
    for part in score.parts:
        key = ('drums' if part.percussion else part.instrument
               if part.instrument in ('singing-voice','singing-chorus') else
               f'gm:{part.program}' if part.program is not None else 'unknown')
        for note in part.notes:
            event_count += 1
            if event_count > 200000:
                raise ValueError('Benchmark score exceeds 200000 notes')
            grouped[key].append((note.pitch, note.start_ms + score.offset_ms,
                                 note.start_ms + note.duration_ms + score.offset_ms))
    return grouped


def _match(reference, prediction, onset_ms, offset_ms):
    if len(reference) > 20000 or len(prediction) > 20000:
        raise ValueError("Benchmark instrument exceeds 20000 events")
    """One-to-one maximum-cardinality matching, not greedy order-dependent matching."""
    # Index notes by pitch and onset. Matching only searches candidates within
    # the onset tolerance, rather than comparing every pair of notes in a mix.
    by_pitch = defaultdict(list)
    for j, (pitch, start, end) in enumerate(reference):
        by_pitch[pitch].append((start, j, end))
    for entries in by_pitch.values():
        entries.sort()
    starts_by_pitch = {pitch: [entry[0] for entry in entries]
                       for pitch, entries in by_pitch.items()}
    adjacency = []
    candidate_count = 0
    # A dense polyphonic passage may otherwise create a quadratic graph even
    # when the note-count cap is respected. Reject inconclusive workloads.
    max_candidates = 1_000_000
    for pitch, start, end in prediction:
        entries = by_pitch.get(pitch, ())
        starts = starts_by_pitch.get(pitch, ())
        lo = bisect_left(starts, start-onset_ms)
        hi = bisect_right(starts, start+onset_ms)
        candidates = [j for rs, j, re in entries[lo:hi] if abs(end-re) <= offset_ms]
        candidate_count += len(candidates)
        if candidate_count > max_candidates:
            raise ValueError("Benchmark matching graph exceeds 1000000 candidate pairs")
        adjacency.append(sorted(candidates,
                                key=lambda j: (abs(start-reference[j][1])+abs(end-reference[j][2]), j)))
    assigned = {}
    # Iterative augmenting paths: dense repeated-note passages must not exceed
    # Python recursion depth or crash benchmarking jobs.
    traversal_count = 0
    max_traversals = 2_000_000
    for source in range(len(prediction)):
        queue = [source]
        previous = {source: None}
        discovered_references = set()
        finish = None
        head = 0
        while head < len(queue) and finish is None:
            candidate = queue[head]
            head += 1
            for reference_index in adjacency[candidate]:
                traversal_count += 1
                if traversal_count > max_traversals:
                    raise ValueError("Benchmark matching search exceeds 2000000 traversals")
                if reference_index in discovered_references:
                    continue
                discovered_references.add(reference_index)
                if reference_index not in assigned:
                    finish = (candidate, reference_index)
                    break
                alternate = assigned[reference_index]
                if alternate not in previous:
                    previous[alternate] = (candidate, reference_index)
                    queue.append(alternate)
        if finish is not None:
            candidate, reference_index = finish
            while True:
                assigned[reference_index] = candidate
                predecessor = previous[candidate]
                if predecessor is None:
                    break
                candidate, reference_index = predecessor
    return len(assigned)


def _diagnose_errors(ref, pred, onset_ms):
    """Relaxed *diagnostics only*: never influence the strict quality metrics.

    Each count is an independent upper-bound signal, not a matched-note score.
    Pitch matches require equal GM identity; program-agnostic onset matches
    indicate possible instrument-label confusion, never a passing prediction.
    """
    ref_notes = [(key, pitch, start, end) for key, notes in ref.items()
                 for pitch, start, end in notes]
    pred_notes = [(key, pitch, start, end) for key, notes in pred.items()
                  for pitch, start, end in notes]
    ref_identity = {(key, pitch) for key, pitch, _, _ in ref_notes}
    ref_pitches = {pitch for _, pitch, _, _ in ref_notes}
    # Use a bounded linear-ish indexed search instead of a full O(N^2) scan.
    by_pitch = defaultdict(list)
    for key, pitch, start, _ in ref_notes:
        by_pitch[pitch].append((start, key))
    for v in by_pitch.values():
        v.sort()
    starts = {p: [x[0] for x in v] for p, v in by_pitch.items()}
    identity_pitch = sum((key, pitch) in ref_identity for key, pitch, _, _ in pred_notes)
    pitch_any = sum(pitch in ref_pitches for _, pitch, _, _ in pred_notes)
    onset_any = onset_same_identity = 0
    for key, pitch, start, _ in pred_notes:
        arr = by_pitch.get(pitch, ())
        positions = starts.get(pitch, ())
        lo = bisect_left(positions, start-onset_ms)
        hi = bisect_right(positions, start+onset_ms)
        if hi > lo:
            onset_any += 1
            if any(rkey == key for _, rkey in arr[lo:hi]):
                onset_same_identity += 1
    return {'predictions_with_pitch_in_reference': pitch_any,
            'predictions_with_program_and_pitch_in_reference': identity_pitch,
            'predictions_with_pitch_and_onset_any_program': onset_any,
            'predictions_with_program_pitch_and_onset': onset_same_identity,
            'note': 'Non-exclusive diagnostic overlaps; no duration matching or one-to-one assignment. Not accuracy, recall, or evidence of instrument separation.'}


def evaluate(reference: MusicResult, prediction: MusicResult, *, onset_ms: float = 50,
             offset_ms: float = 100):
    if (type(onset_ms) not in (int, float) or not math.isfinite(onset_ms)
            or type(offset_ms) not in (int, float) or not math.isfinite(offset_ms)
            or not 0 <= onset_ms <= 1000 or not 0 <= offset_ms <= 2000):
        raise ValueError('Invalid benchmark matching tolerance')
    ref, pred = _events(reference), _events(prediction)
    instrument_rows = []
    total_tp = total_ref = total_pred = 0
    for instrument in sorted(ref.keys() | pred.keys()):
        r, p = ref.get(instrument, []), pred.get(instrument, [])
        tp = _match(r, p, onset_ms, offset_ms)
        total_tp += tp
        total_ref += len(r)
        total_pred += len(p)
        ip = tp / len(p) if p else 0.0
        ir = tp / len(r) if r else 0.0
        instrument_rows.append({'instrument': instrument, 'precision': ip, 'recall': ir,
                                'f1': 2*ip*ir/(ip+ir) if ip+ir else 0.0, 'reference_notes': len(r),
                                'predicted_notes': len(p), 'matched_notes': tp,
                                'false_positives': len(p)-tp, 'false_negatives': len(r)-tp})
    precision = total_tp / total_pred if total_pred else 0.0
    recall = total_tp / total_ref if total_ref else 0.0
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
    return {'protocol': 'mta-midi-benchmark-1', 'onset_tolerance_ms': onset_ms,
            'offset_tolerance_ms': offset_ms, 'reference_instruments': len(ref),
            'predicted_instruments': len(pred), 'matched_notes': total_tp,
            'reference_notes': total_ref, 'predicted_notes': total_pred,
            'precision': precision, 'recall': recall, 'f1': f1,
            'by_instrument': instrument_rows,
            'error_diagnostics': _diagnose_errors(ref, pred, onset_ms),
            'limits': ['Matching uses pitch, onset, offset and GM program; it does not measure timbre quality.',
                       'Two performers with the same GM program are not distinguishable by this metric.',
                       'Drum notes are grouped by percussion flag; calibrated confidence is not inferred.',
                       'Explicit singing classes are distinct from their generated GM playback proxies.']}


def evaluate_files(reference_path: Path, prediction_path: Path, **kwargs):
    """Compare locally supplied scores and bind the report to their exact bytes.

    Fingerprints attest reproducibility of the input files, not that the files
    were produced by a real neural model or represent independently reviewed
    ground truth.
    """
    scores = []
    sources = []
    for path in (Path(reference_path), Path(prediction_path)):
        # Open the verified inode, not a pathname checked before opening: a
        # concurrent replacement must not redirect a benchmark to another file.
        # O_NONBLOCK avoids hanging on accidentally supplied FIFOs.
        flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)
        if hasattr(os, 'O_NOFOLLOW'):
            flags |= os.O_NOFOLLOW
        if path.is_symlink():
            raise ValueError('Benchmark input must be a regular MusicResult JSON up to 16 MiB')
        try:
            fd = os.open(path, flags)
            with os.fdopen(fd, 'rb') as handle:
                metadata = os.fstat(handle.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 16 * 1024 * 1024:
                    raise ValueError('Benchmark input must be a regular MusicResult JSON up to 16 MiB')
                raw = handle.read(16 * 1024 * 1024 + 1)
                after = os.fstat(handle.fileno())
                if (len(raw) != metadata.st_size or after.st_size != metadata.st_size
                        or after.st_mtime_ns != metadata.st_mtime_ns
                        or after.st_ctime_ns != metadata.st_ctime_ns):
                    raise ValueError('Benchmark input changed during reading')
        except OSError as exc:
            raise ValueError('Benchmark input cannot be safely opened as a regular JSON file') from exc
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError('Benchmark input must be a regular MusicResult JSON up to 16 MiB')
        scores.append(parse_result(raw))
        sources.append({'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    report = evaluate(*scores, **kwargs)
    report['input_provenance'] = {'reference': sources[0], 'prediction': sources[1],
        'statement': 'File hashes only; model inference and reference review are not certified.'}
    return report
