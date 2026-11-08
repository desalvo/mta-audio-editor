/* Read-only diagnostics for lyric timing, including Merish's 10 ms clock. */
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

  root.MtaLyricsTiming = {issues, previewLine};
})(typeof window === 'undefined' ? globalThis : window);
