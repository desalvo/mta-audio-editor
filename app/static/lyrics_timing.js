/* Lyric timing diagnostics and explicit repairs on Merish's 10 ms clock. */
(function (root) {
  'use strict';

  const tick = value => Math.floor(value / 10) * 10;
  const validTime = value => Number.isFinite(value) && value >= 0;

  function issues(lines, durationMs = 0, highlight = 'word') {
    const result = [];
    const active = lines.map((line, index) => ({line, index}))
      .filter(({line}) => !line.disabled && !line.deleted && String(line.text || '').trim())
      .sort((a, b) => a.line.time_ms - b.line.time_ms);

    active.forEach(({line, index}, position) => {
      const add = (code, wordIndex = null, extra = {}) => {
        result.push({lineIndex: index, wordIndex, code, ...extra});
      };
      const start = line.time_ms;
      const next = active[position + 1];
      const nextStart = next ? tick(next.line.time_ms) : Infinity;
      const audioEnd = durationMs > 0 ? durationMs : Infinity;
      if (!validTime(start)) add('line_start');
      if (line.end_ms != null && (!validTime(line.end_ms) || line.end_ms <= start)) add('line_duration');
      if (start >= audioEnd) add('line_after_audio', null, {limit: audioEnd});
      if (next && tick(start) === tick(next.line.time_ms)) {
        const code = start === next.line.time_ms ? 'line_duplicate' : 'line_precision';
        add(code, null, {otherLineIndex: next.index});
        result.push({lineIndex: next.index, wordIndex: null, code, otherLineIndex: index});
      }

      let previousEnd = start;
      (line.words || []).forEach((word, wordIndex) => {
        const wordStart = word.start_ms;
        const wordEnd = word.end_ms;
        const times = {start: wordStart, end: wordEnd};
        if (!validTime(wordStart) || !validTime(wordEnd) || tick(wordEnd) <= tick(wordStart)) {
          add('word_duration', wordIndex, times);
        }
        if (tick(wordStart) < tick(start)) add('word_before_line', wordIndex, {...times, limit: start});
        if (wordIndex > 0 && (wordStart < previousEnd || tick(wordStart) < tick(previousEnd))) {
          add('word_overlap', wordIndex, {...times, limit: previousEnd, previousWordIndex: wordIndex - 1});
        }
        if (line.end_ms != null && wordEnd > line.end_ms) {
          add('word_after_line', wordIndex, {...times, limit: line.end_ms});
        }
        if (next && wordEnd > nextStart) {
          add('word_after_next_line', wordIndex, {...times, limit: nextStart, otherLineIndex: next.index});
        }
        if (wordEnd > audioEnd) add('word_after_audio', wordIndex, {...times, limit: audioEnd});

        if (highlight === 'character') {
          let syllableEnd = wordStart;
          (word.syllables || []).forEach((syllable, syllableIndex) => {
            if (!validTime(syllable.start_ms) || !validTime(syllable.end_ms)
                || tick(syllable.end_ms) <= tick(syllable.start_ms)
                || tick(syllable.start_ms) < tick(syllableEnd)
                || syllable.start_ms < syllableEnd || syllable.end_ms > wordEnd) {
              add('syllable_timing', wordIndex, {
                syllableIndex, start: syllable.start_ms, end: syllable.end_ms, limit: wordEnd,
              });
            }
            syllableEnd = syllable.end_ms;
          });
        }
        previousEnd = wordEnd;
      });
    });
    return result;
  }

  // Preview precisely the word timing retained by saveTimedEditor. A translated
  // row retains translated words, while text or duration edits discard them.
  function previewLine(original, start, end, text) {
    const line = {...(original || {}), time_ms: start, end_ms: end, text, words: []};
    if (!original || String(original.text || '') !== text) return line;
    const delta = start - Number(original.time_ms);
    const sameEnd = original.end_ms == null ? end == null
      : end != null && end - Number(original.end_ms) === delta;
    if (!sameEnd) return line;
    const words = JSON.parse(JSON.stringify(original.words || []));
    if (!words.every(word => word.start_ms + delta >= 0 && word.end_ms + delta >= 0
        && (word.syllables || []).every(syllable => syllable.start_ms + delta >= 0 && syllable.end_ms + delta >= 0))) {
      return line;
    }
    words.forEach(word => {
      word.start_ms += delta;
      word.end_ms += delta;
      (word.syllables || []).forEach(syllable => {
        syllable.start_ms += delta;
        syllable.end_ms += delta;
      });
    });
    line.words = words;
    return line;
  }

  function repair(lines, durationMs = 0, highlight = 'word', selected = null) {
    const before = issues(lines, durationMs, highlight);
    const wanted = selected ? before.filter(issue => issue.lineIndex === selected.lineIndex
      && issue.wordIndex === selected.wordIndex && issue.code === selected.code
      && (issue.syllableIndex ?? null) === (selected.syllableIndex ?? null)) : before;
    if (!wanted.length) return {ok: true, lines, changedLines: [], remaining: before};
    const repaired = JSON.parse(JSON.stringify(lines));
    const active = repaired.map((line, index) => ({line, index}))
      .filter(({line}) => !line.disabled && !line.deleted && String(line.text || '').trim())
      .sort((a, b) => (a.line.time_ms || 0) - (b.line.time_ms || 0));
    const ceil = value => Math.ceil(value / 10) * 10;
    const audioEnd = durationMs > 0 ? tick(durationMs) : Infinity;
    const needed = word => Math.max(1, (word.syllables || []).length) * 10;
    const minimum = line => Math.max(10, (line.words || []).reduce((sum, word) => sum + needed(word), 0));
    const fail = lineIndex => { throw {code: 'insufficient_space', lineIndex}; };

    // Allocate at least one clock interval to each segment. Keep valid original
    // times where possible and reserve enough room for all following segments.
    function fit(segments, lower, upper, widths, lineIndex) {
      lower = ceil(lower);
      upper = Number.isFinite(upper) ? tick(upper) : Infinity;
      const required = widths.reduce((sum, width) => sum + width, 0);
      if (!Number.isFinite(lower) || upper - lower < required) fail(lineIndex);
      let cursor = lower;
      let remaining = required;
      segments.forEach((segment, index) => {
        const width = widths[index];
        const latestStart = upper - remaining;
        const oldStart = validTime(segment.start_ms) ? segment.start_ms : cursor;
        const start = oldStart >= cursor && oldStart <= latestStart ? oldStart
          : Math.max(cursor, Math.min(latestStart, ceil(oldStart)));
        remaining -= width;
        const earliestEnd = ceil(start) + width;
        const nextStart = segments[index + 1]?.start_ms;
        const keepNextStart = validTime(nextStart) && tick(nextStart) >= earliestEnd;
        const latestEnd = Math.min(upper - remaining, keepNextStart ? tick(nextStart) : Infinity);
        if (earliestEnd > latestEnd) fail(lineIndex);
        const oldEnd = validTime(segment.end_ms) ? segment.end_ms : earliestEnd;
        const end = oldEnd >= earliestEnd && oldEnd <= latestEnd ? oldEnd
          : Math.max(earliestEnd, Math.min(latestEnd, tick(oldEnd)));
        segment.start_ms = start;
        segment.end_ms = end;
        cursor = end;
      });
    }

    function bounds(position) {
      const line = active[position].line;
      const next = active[position + 1];
      const end = Math.min(audioEnd, next ? tick(next.line.time_ms) : Infinity,
        validTime(line.end_ms) ? line.end_ms : Infinity);
      return [line.time_ms, end];
    }

    function repairSyllables(word, lineIndex) {
      const syllables = word.syllables || [];
      if (syllables.length) fit(syllables, word.start_ms, word.end_ms, syllables.map(() => 10), lineIndex);
    }

    try {
      // Start collisions are resolved on the later line, keeping chronological
      // order and using the previous line's last word as the preferred boundary.
      const startCodes = new Set(['line_start', 'line_after_audio', 'line_duplicate', 'line_precision']);
      const positions = new Set();
      wanted.filter(issue => startCodes.has(issue.code)).forEach(issue => {
        let position = active.findIndex(item => item.index === issue.lineIndex);
        if (issue.otherLineIndex != null) {
          position = Math.max(position, active.findIndex(item => item.index === issue.otherLineIndex));
        }
        positions.add(position);
      });
      for (const position of [...positions].sort((a, b) => a - b)) {
        const {line, index} = active[position];
        const previous = active[position - 1]?.line;
        const next = active.find((item, nextPosition) => nextPosition > position && !positions.has(nextPosition))?.line;
        const lower = previous ? ceil(previous.time_ms) + minimum(previous) : 0;
        const upper = Math.min(audioEnd, next ? tick(next.time_ms) : Infinity) - minimum(line);
        if (upper < lower) fail(index);
        const previousEnd = Math.max(lower, ...(previous?.words || []).map(word => validTime(word.end_ms) ? ceil(word.end_ms) : lower));
        const desired = validTime(line.time_ms) ? line.time_ms : lower;
        const preferred = Math.max(desired, previousEnd);
        line.time_ms = Math.max(lower, Math.min(upper, ceil(preferred)));
      }

      const targetPositions = new Set(wanted.map(issue => active.findIndex(item => item.index === issue.lineIndex)));
      // Moving a line boundary can require fitting words on either side.
      for (const position of positions) {
        targetPositions.add(position);
        if (position > 0) targetPositions.add(position - 1);
      }
      for (const position of [...targetPositions].sort((a, b) => a - b)) {
        const {line, index} = active[position];
        let [lower, upper] = bounds(position);
        const nextLimit = Math.min(audioEnd, active[position + 1] ? tick(active[position + 1].line.time_ms) : Infinity);
        if (line.end_ms != null && (!validTime(line.end_ms) || line.end_ms <= lower)) {
          const desiredEnd = Math.max(lower + minimum(line), ...(line.words || []).map(word => validTime(word.end_ms) ? ceil(word.end_ms) : lower));
          line.end_ms = Math.min(nextLimit, desiredEnd);
          upper = Math.min(nextLimit, line.end_ms);
        }
        const currentIssues = issues(repaired, durationMs, highlight).filter(issue => issue.lineIndex === index);
        const wordIssues = currentIssues.filter(issue => issue.wordIndex != null);
        if (!wordIssues.length) continue;
        const words = line.words || [];
        const repairWholeLine = !selected || selected.wordIndex == null || positions.size > 0;
        if (repairWholeLine) {
          fit(words, lower, upper, words.map(needed), index);
          words.forEach(word => repairSyllables(word, index));
        } else {
          const wordIndex = selected.wordIndex;
          const word = words[wordIndex];
          if (!word) fail(index);
          try {
            if (selected.code === 'word_overlap' && wordIndex > 0) {
              const previous = words[wordIndex - 1];
              const previousLower = wordIndex > 1 ? words[wordIndex - 2].end_ms : lower;
              fit([previous], Math.max(lower, previousLower), Math.min(upper, word.start_ms), [needed(previous)], index);
              repairSyllables(previous, index);
            } else if (selected.code !== 'syllable_timing') {
              const previousEnd = wordIndex > 0 ? words[wordIndex - 1].end_ms : lower;
              const nextStart = wordIndex + 1 < words.length ? words[wordIndex + 1].start_ms : upper;
              fit([word], Math.max(lower, previousEnd), Math.min(upper, nextStart), [needed(word)], index);
            }
            repairSyllables(word, index);
          } catch (reason) {
            if (reason.code !== 'insufficient_space') throw reason;
            // A neighbouring word can occupy the last few clock intervals.
            // Shorten the connected sequence to make room within this line.
            fit(words, lower, upper, words.map(needed), index);
            words.forEach(item => repairSyllables(item, index));
          }
        }
      }
      const remaining = issues(repaired, durationMs, highlight);
      const key = issue => [issue.lineIndex, issue.wordIndex, issue.code, issue.syllableIndex ?? null].join(':');
      const originalKeys = new Set(before.map(key));
      const wantedKeys = new Set(wanted.map(key));
      if ((!selected && remaining.length) || remaining.some(issue => wantedKeys.has(key(issue)) || !originalKeys.has(key(issue)))) {
        fail(selected?.lineIndex ?? remaining[0]?.lineIndex ?? 0);
      }
      const changedLines = repaired.map((line, index) => JSON.stringify(line) !== JSON.stringify(lines[index]) ? index : -1)
        .filter(index => index >= 0);
      return {ok: true, lines: repaired, changedLines, remaining};
    } catch (reason) {
      if (reason.code !== 'insufficient_space') throw reason;
      return {ok: false, lines, changedLines: [], remaining: before, reason};
    }
  }

  root.MtaLyricsTiming = {issues, previewLine, repair};
})(typeof window === 'undefined' ? globalThis : window);
