"""Project content modes and reversible conversion, independent of playback."""
TARGETS = ('DAW', 'DAW_MIDI', 'MIDI', 'MTA8', 'MTA16')


class ProjectKindError(ValueError):
    pass


def allows(target, kind):
    return target == 'DAW_MIDI' or (target == 'MIDI' and kind == 'midi') or (target in ('DAW', 'MTA8', 'MTA16') and kind == 'audio')


def require_kind(project, kind):
    if not allows(project.target, kind):
        raise ProjectKindError('This project type does not allow '+kind+' tracks. Convert the project type in Project info first.')


def migrate_legacy(project):
    """Existing mixed/audio-MIDI documents retain every active track on upgrade."""
    if project.project_kind_version == 0:
        if any(not allows(project.target, t.kind) for t in project.tracks):
            project.target = 'DAW_MIDI'
        project.project_kind_version = 1
    return project


def validate(project):
    for track in project.tracks:
        require_kind(project, track.kind)
    ids = [t.id for t in [*project.tracks, *project.archived_tracks]]
    if len(ids) != len(set(ids)):
        raise ProjectKindError('Duplicate active or preserved track id')


def convert(project, target):
    if target not in TARGETS:
        raise ProjectKindError('Invalid project type')
    # Retain complete track objects, including all MIDI events, expression,
    # original media references and plugins. Inactive tracks never enter playback.
    pool = [*project.tracks, *project.archived_tracks]
    active = [t for t in pool if allows(target, t.kind)]
    inactive = [t for t in pool if not allows(target, t.kind)]
    if max(len(active), len(inactive)) > 1024:
        raise ProjectKindError('Conversion exceeds the 1024-track limit; no tracks were changed.')
    project.tracks = active
    project.archived_tracks = inactive
    project.target = target
    project.project_kind_version = 1
    validate(project)
    return project
