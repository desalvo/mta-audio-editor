"""Route combined model parts without sharing melodic channels accidentally.

This changes transport addresses only. Notes, labels, alternatives and the
inferred instrument count are not changed. MIDI 1.0 has 15 melodic channels.
"""


def route_parts(parts):
    channels=[channel for channel in range(16) if channel!=9]
    next_channel=0
    routed=[]
    for part in parts:
        used=sorted({note.channel for note in part.notes} |
                    {control.data[0]&15 for control in part.controls})
        mapping={}
        for original in used:
            mapping[original]=9 if part.percussion else channels[next_channel%len(channels)]
            if not part.percussion:next_channel+=1
        notes=[note.model_copy(update={'channel':mapping[note.channel]}) for note in part.notes]
        controls=[control.model_copy(update={'data':[
            (control.data[0]&0xF0)|mapping[control.data[0]&15],*control.data[1:]]})
            for control in part.controls]
        routed.append(part.model_copy(deep=True,update={'notes':notes,'controls':controls}))
    warnings=[]
    if next_channel>15:
        warnings.append('Combined transcription exceeds 15 melodic MIDI channels; channel addresses are reused. '
                        'Use per-track instruments or separate MIDI ports for independent playback.')
    return routed,warnings
