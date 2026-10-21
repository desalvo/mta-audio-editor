"""Bounded MT3 event decoding with independent GM and drum identities.

MT3 event semantics: https://github.com/magenta/mt3 (Apache-2.0).
No program labels or correctness probabilities are inferred by this decoder.
"""
import math


def decode(predictions, codec, duration):
    if not math.isfinite(duration) or not 0<duration<=600:
        raise ValueError('Invalid MT3 source duration')
    if len(predictions)>300:
        raise ValueError('MT3 window budget exceeded')
    active={};notes=[];invalid=dropped=unclosed=0;last_time=0.;previous=-1.;budget=0

    def finish(key,end):
        start,velocity=active.pop(key)
        end=min(duration,max(end,start+.01))
        if end>start:
            program,pitch=key
            notes.append(dict(pitch=pitch,start_time=start,end_time=end,velocity=velocity,program=program,is_drum=False))
        if len(notes)>75000:raise ValueError('MT3 musical event budget exceeded')

    for index,prediction in enumerate(predictions):
        start=float(prediction['start_time'])
        if not math.isfinite(start) or start<0 or start<=previous:
            raise ValueError('MT3 windows must have increasing finite source times')
        previous=start
        boundary=min(duration,float(predictions[index+1]['start_time'])) if index+1<len(predictions) else duration
        if not math.isfinite(boundary) or boundary<=start:
            raise ValueError('Invalid MT3 window boundary')
        program=0;velocity=0;steps=0;current=start;tied=set();tie_section=True
        for token in prediction['est_tokens']:
            budget+=1
            if budget>310000:raise ValueError('MT3 token budget exceeded')
            try:event=codec.decode_event_index(int(token))
            except (ValueError,TypeError,OverflowError):invalid+=1;continue
            kind,value=event.type,event.value
            if kind=='shift':
                steps+=value;current=start+steps/codec.steps_per_second
                if current>boundary:dropped+=1;break
                last_time=max(last_time,current)
                continue
            steps=0
            if kind=='program':program=value
            elif kind=='velocity':velocity=0 if value==0 else 127
            elif kind=='tie':
                if not tie_section:invalid+=1;continue
                for key in list(active):
                    if key not in tied:finish(key,start)
                tie_section=False
            elif kind=='pitch':
                key=(program,value)
                if tie_section:
                    if key not in active or key in tied:invalid+=1
                    else:tied.add(key)
                elif velocity==0:
                    if key not in active:invalid+=1
                    else:finish(key,current)
                else:
                    if current>=duration:dropped+=1;continue
                    if key in active:finish(key,current)
                    active[key]=(current,velocity)
            elif kind=='drum':
                # MT3 drum tokens encode onsets, not sustained note-off pairs.
                # GM program 9 remains melodic; it is never a percussion key.
                if tie_section or velocity==0:invalid+=1;continue
                end=min(duration,current+.01)
                if end>current:
                    notes.append(dict(pitch=value,start_time=current,end_time=end,velocity=velocity,program=0,is_drum=True))
            else:invalid+=1
            last_time=max(last_time,current)
            if len(notes)+len(active)>75000:raise ValueError('MT3 musical event budget exceeded')
        if tie_section:
            invalid+=1
    for key in list(active):
        finish(key,last_time);unclosed+=1
    return notes,{'invalid_events':invalid,'dropped_events':dropped,'unclosed_notes':unclosed}
