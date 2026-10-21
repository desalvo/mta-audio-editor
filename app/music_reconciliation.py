"""Conservative one-to-one reconciliation of independently produced scores.

Agreement is an observed vote, never a calibrated probability. Original model
hypotheses remain available, including instrument conflicts and unmatched notes.
"""
from collections import defaultdict
import hashlib
from pydantic import BaseModel, ConfigDict, Field

from .music_interchange import MusicResult, parse_result


class Tolerances(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    onset_ms: float = Field(default=60., ge=5, le=250, allow_inf_nan=False)
    # Piano release tails produced 175–185 ms offset disagreement in the real
    # two-model fixture while onsets agreed within 12 ms. Keep primary timing,
    # preserve originals, and permit this release-tail difference by default.
    offset_ms: float = Field(default=200., ge=10, le=1000, allow_inf_nan=False)


class ReconciliationSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    default: Tolerances = Field(default_factory=Tolerances)
    # Per-instrument overrides; no universal confidence threshold.
    instruments: dict[str, Tolerances] = Field(default_factory=dict, max_length=129)


def _id(*values):
    return hashlib.sha256(':'.join(map(str, values)).encode()).hexdigest()[:24]


def reconcile(hypotheses, settings=None):
    """First model supplies primary timing; preserve all original alternatives."""
    cfg = ReconciliationSettings.model_validate(settings or {})
    if any(k != 'drums' and (not k.isdecimal() or not 0 <= int(k) <= 127) for k in cfg.instruments):
        raise ValueError('Instrument tolerance keys must be GM programs 0–127 or drums')
    if not isinstance(hypotheses, list) or not 2 <= len(hypotheses) <= 4:
        raise ValueError('Reconciliation requires two to four independent model results')
    names = [name for name, _ in hypotheses]
    if any(not isinstance(name, str) or not name or len(name) > 80 for name in names) or len(set(names)) != len(names):
        raise ValueError('Independent, unique model identifiers required')
    results = [parse_result(value) if isinstance(value, dict) else MusicResult.model_validate(value)
               for _, value in hypotheses]
    if len({r.offset_ms for r in results}) != 1:
        raise ValueError('Model hypotheses must share the same source region offset')
    if sum(len(r.parts)+len(r.alternatives) for r in results) > 128:
        raise ValueError('Too many model alternatives; process fewer sources in one job')
    nonempty=[(name,result) for name,result in zip(names,results) if result.parts]
    if len(nonempty)<2:
        from .music_interchange import no_notes
        warning='One or more models detected no notes; no cross-model agreement is claimed.'
        result=nonempty[0][1].model_copy(deep=True) if nonempty else no_notes()
        result.offset_ms=results[0].offset_ms
        result.warnings=list(dict.fromkeys(w for value in results for w in value.warnings))[:199]
        result.warnings=list(dict.fromkeys([*result.warnings,warning]))[:200]
        return result,{'protocol':'mta-reconciliation-1','models':names,'comparisons':[],
                      'empty_models':[name for name,result in zip(names,results) if not result.parts],
                      'calibrated_confidence':False,'policy':'retain the nonempty hypothesis; no inferred agreement'}
    # A silent preferred backend must not prevent the other two actual models
    # from being compared. Preserve every model in the audit and alternatives.
    if not results[0].parts:
        first=next(i for i,result in enumerate(results) if result.parts)
        names=[names[first],*names[:first],*names[first+1:]]
        results=[results[first],*results[:first],*results[first+1:]]
    parts = [p.model_copy(deep=True, update={'id':'main-'+_id(names[0], p.id)}) for p in results[0].parts]
    alternatives = []
    for name, result in zip(names, results):
        for part in [*result.parts, *result.alternatives]:
            alternatives.append(part.model_copy(deep=True, update={
                'id':'alt-'+_id(name, part.id), 'source_model':name, 'review':'unreviewed'}))
    report = {'protocol':'mta-reconciliation-1','models':names,'primary_model':names[0],
              'empty_models':[name for name,result in zip(names,results) if not result.parts],
              'comparisons':[],
              'policy':'primary-timing; primary-only reference votes; one-to-one matches; retain originals and unmatched events',
              'calibrated_confidence':False}
    comparisons = 0
    primary_voters = defaultdict(set)
    primary_parts_count = len(parts)
    for name, result in zip(names[1:], results[1:]):
        buckets = defaultdict(list)
        # Candidate index uses fixed 250 ms bins, the maximum onset tolerance.
        for pi, part in enumerate(parts[:primary_parts_count]):
            for ni, note in enumerate(part.notes):
                buckets[(part.percussion, note.pitch, int(note.start_ms//250))].append((pi, ni, note))
        used = set(); matched = conflicts = ambiguous = unmatched = 0
        additions = []
        for part in result.parts:
            remaining = []
            tolerance = cfg.instruments.get('drums' if part.percussion else str(part.program), cfg.default)
            for note in part.notes:
                candidates = []
                for bucket in range(int(note.start_ms//250)-1, int(note.start_ms//250)+2):
                    for pi, ni, original in buckets[(part.percussion, note.pitch, bucket)]:
                        comparisons += 1
                        if comparisons > 2000000:
                            raise ValueError('Dense transcription exceeds reconciliation comparison budget')
                        if (pi, ni) in used:continue
                        if abs(note.start_ms-original.start_ms) > tolerance.onset_ms:continue
                        if abs(note.start_ms+note.duration_ms-original.start_ms-original.duration_ms) > tolerance.offset_ms:continue
                        original_part = parts[pi]
                        if part.program is not None and original_part.program is not None and part.program != original_part.program:
                            conflicts += 1;continue
                        candidates.append((abs(note.start_ms-original.start_ms), pi, ni))
                candidates.sort()
                # Even a known GM program cannot identify which of two unison
                # performers played a note. Preserve the competing event.
                if len(candidates) > 1:
                    ambiguous += 1;remaining.append(note);continue
                if candidates:
                    _, pi, ni = candidates[0];used.add((pi, ni));matched += 1
                    primary_voters[(pi, ni)].add(name)
                else:
                    unmatched += 1;remaining.append(note)
            if remaining or part.controls:
                additions.append(part.model_copy(deep=True, update={
                    'id':'extra-'+_id(name, part.id), 'name':part.name[:160]+' ['+name[:30]+']',
                    'notes':remaining, 'source_model':name, 'review':'unreviewed'}))
        parts.extend(additions)
        report['comparisons'].append({'model':name,'matched_events':matched,'unmatched_events':unmatched,
                                     'instrument_conflicts':conflicts,'ambiguous_events':ambiguous})
    primary_total = sum(len(part.notes) for part in parts[:primary_parts_count])
    confirmed = sum(bool(voters) for voters in primary_voters.values())
    report['primary_audit'] = {
        'primary_note_count': primary_total,
        'notes_supported_by_other_model': confirmed,
        'notes_without_other_model_support': primary_total - confirmed,
        'support_distribution': {str(count): sum(len(v) == count for v in primary_voters.values())
                                 for count in range(1, len(names))},
        'meaning': 'Observed cross-model matches only; not a correctness score or calibrated confidence',
    }
    warnings = [w for r in results for w in r.warnings]
    warnings += ['Model agreement is not a probability of correctness. Primary timing is retained.',
                 'All original model hypotheses are preserved as editable alternatives; review unassigned instruments and conflicts.']
    for row in report['comparisons']:
        warnings.append(f"{row['model']}: {row['matched_events']} matched, {row['unmatched_events']} unmatched, "
                        f"{row['instrument_conflicts']} instrument conflicts, {row['ambiguous_events']} ambiguous events.")
    return MusicResult(parts=parts, alternatives=alternatives, offset_ms=results[0].offset_ms,
                       warnings=list(dict.fromkeys(warnings))[:200]), report
