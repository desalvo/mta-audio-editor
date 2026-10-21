"""Source-domain quarter-note clock shared with the visible musical transport."""
import bisect
import math

from .musical_clock import MusicalClock


class TempoMap:
    def __init__(self, data):
        self.clock = MusicalClock(data)
        self.times = self.clock.times
        self.pieces = []
        for p in self.clock.sections:
            anchor = self.clock.anchors[max(0, bisect.bisect_right(self.clock.anchor_times, p['at'])-1)]
            self.pieces.append((p['quarter_bpm'], p['n'], p['d'], p['q'], anchor['q']))

    def position(self, ms):
        i = max(0, bisect.bisect_right(self.times, ms)-1)
        bpm, n, d, ppq, origin = self.pieces[i]
        ppq += (ms-self.times[i])*bpm/60000
        bar = n*4/d
        return bpm, n, d, ppq, origin+math.floor((ppq-origin)/bar+1e-10)*bar

    def boundaries(self, start, count, rate):
        end = start+count
        return sorted({start, end, *[round(t*rate/1000) for t in self.times if start < round(t*rate/1000) < end]})
