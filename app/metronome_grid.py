"""Metronome-only tempo settings; never modify project audio tempo or pitch."""
SIGNATURES = ('2/4', '3/4', '4/4', '5/4', '6/8', '7/8', '9/8', '12/8')


def grid_settings(project):
    if project.metronome_mode == 'adaptive':
        return float(project.bpm), project.time_signature
    return float(project.metronome_bpm or project.bpm), project.metronome_time_signature or project.time_signature


def manual_signature(project, left, right):
    values = project.metronome_manual_zone_signatures
    exact = f'{left}|{right}'
    if exact in values:
        return values[exact]
    candidates = [v for k, v in values.items() if k.split('|')[0] == left or k.split('|')[-1] == right]
    return candidates[0] if len(candidates) == 1 else None


def zone_signature(project, left, right):
    return manual_signature(project, left, right) or grid_settings(project)[1]
