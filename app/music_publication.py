"""Shared revision guard for non-destructive musical result imports."""
import hashlib
import json
import re
import uuid


def parse_import(data):
    """Validate off the event loop; defaults must not break idempotent retries."""
    from .music_interchange import MusicResult
    body = json.loads(data)
    if not isinstance(body, dict) or set(body) != {'publication_id', 'expected_revision', 'result'}:
        raise ValueError('Invalid musical import')
    publication, expected = body['publication_id'], body['expected_revision']
    if not isinstance(publication, str) or not re.fullmatch('[a-f0-9]{32}', publication):
        raise ValueError('Invalid publication identifier')
    if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
        raise ValueError('Invalid project revision')
    result = body['result']
    if isinstance(result, dict):
        for kind in ('parts', 'alternatives'):
            parts = result.get(kind, [])
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict) or not isinstance(part.get('notes', []), list):
                    continue
                for i, note in enumerate(part.get('notes', [])):
                    if isinstance(note, dict) and 'id' not in note:
                        note['id'] = uuid.uuid5(uuid.UUID(publication), f'{kind}:{part.get("id", "")}:{i}').hex
    return publication, expected, MusicResult.model_validate(result)


def revision(project):
    return hashlib.sha256(project.model_dump_json().encode()).hexdigest()


def result_digest(result):
    return hashlib.sha256(json.dumps(result.model_dump(mode='json'), sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def generation_for_part(generation, part_id):
    """Keep only the relevant singer receipt on each track, preserving legacy."""
    if not generation or generation.get('schema')!='mta-multi-singer-generation-1':
        return generation
    source=generation.get('part_sources',{}).get(part_id)
    if source not in generation.get('sources',{}):
        raise ValueError('Missing singer-specific generation metadata')
    return {**generation['sources'][source],'source_track_id':source,'region_start_ms':generation.get('region_start_ms',0)}
