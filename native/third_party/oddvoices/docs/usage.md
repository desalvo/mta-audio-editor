# OddVoices usage

To compile OddVoices, see [INSTALL.md](../INSTALL.md).

## Using the command-line frontend

The arguments to the `sing` executable are as follows:

    sing [--help] <voice-file> <cmudict> [-m <in-midi>] [-j <in-json>] [-l <lyrics-txt>] <out-wav>

where:

- `voice-file` is a .voice file compiled with the `oddvoices-compile` Python frontend. See the installation instructions for how to compile a voice.
- `cmudict` is the path to the CMU Pronouncing Dictionary, provided with binary downloads and at the root of the repository as `cmudict-0.7b`.
- `in-midi` is an input MIDI file. More info later in this document.
- `in-json` is an input JSON file. More info later in this document.
- `out-wav` is the output WAV file. No other output formats are supported to avoid a dependency on libsndfile.
- `lyrics-txt` is an optional path to a text file containing lyrics. If not specified, lyrics embedded in the JSON or MIDI file are used. The encoding is ASCII for now -- any non-ASCII bytes are ignored.

You must specify either `-m` or `-j`, but not both.

## Phonetic entry

OddVoices uses the [CMU Pronouncing Dictionary](http://www.speech.cs.cmu.edu/cgi-bin/cmudict/) to pronounce most words. OddVoices does not identify parts of speech, so heteronyms like "lead" and "read" are not handled intelligently. For OOV (out-of-vocabulary) words, OddVoices will guess the pronunciation by converting individual letters and pairs of letters to phonemes.

To supply custom pronunciations to override the defaults, [X-SAMPA](https://en.wikipedia.org/wiki/X-SAMPA) notation is supported. Surround the X-SAMPA pronunciation with forward slashes (like this: /hEloU/ ) and make sure no additional punctuation immediately precedes or follows the slashes. The table of phonemes is:

<table id="phoneme-guide">
<tr><th>X-SAMPA</th><th>IPA</th><th>Pronunciation</th></tr>
<tr><td>/@/, /V/</td><td>/ə/, /ʌ/</td><td>c<strong>u</strong>b</td></tr>
<tr><td>/@`/, /3`/</td><td>/ɚ/, /ɝ/</td><td>b<strong>ir</strong>d</td></tr>
<tr><td>/A/, /O/</td><td>/ɑ/, /ɔ/</td><td>c<strong>augh</strong>t, c<strong>o</strong>t</td></tr>
<tr><td>/D/</td><td>/ð/</td><td>wi<strong>th</strong>er</td></tr>
<tr><td>/E/</td><td>/ɛ/</td><td>l<strong>e</strong>t</td></tr>
<tr><td>/I/</td><td>/ɪ/</td><td>b<strong>i</strong>t</td></tr>
<tr><td>/N/</td><td>/ŋ/</td><td>ha<strong>ng</strong></td></tr>
<tr><td>/OI/</td><td>/ɔɪ/</td><td><strong>oi</strong>l</td></tr>
<tr><td>/S/</td><td>/ʃ/</td><td><strong>sh</strong>ock</td></tr>
<tr><td>/T/</td><td>/θ/</td><td><strong>th</strong>ing</td></tr>
<tr><td>/U/</td><td>/ʊ/</td><td>l<strong>oo</strong>k</td></tr>
<tr><td>/Z/</td><td>/ʒ/</td><td>mea<strong>s</strong>ure</td></tr>
<tr><td>/aI/</td><td>/aɪ/</td><td>l<strong>ie</strong></td></tr>
<tr><td>/aU/</td><td>/aʊ/</td><td><strong>ow</strong>l</td></tr>
<tr><td>/b/</td><td>/b/</td><td><strong>b</strong>ay</td></tr>
<tr><td>/d/</td><td>/d/</td><td><strong>d</strong>ine</td></tr>
<tr><td>/dZ/</td><td>/dʒ/</td><td><strong>j</strong>et</td></tr>
<tr><td>/eI/</td><td>/eɪ/</td><td>h<strong>ay</strong></td>
</tr><tr><td>/f/</td><td>/f/</td><td><strong>f</strong>ast</td></tr>
<tr><td>/g/</td><td>/g/</td><td><strong>g</strong>od</td></tr>
<tr><td>/h/</td><td>/h/</td><td><strong>h</strong>ay</td></tr>
<tr><td>/i/</td><td>/i/</td><td>s<strong>ee</strong>d</td></tr>
<tr><td>/j/</td><td>/j/</td><td><strong>y</strong>ard</td></tr>
<tr><td>/k/</td><td>/k/</td><td><strong>c</strong>ut</td></tr>
<tr><td>/l/</td><td>/l/</td><td><strong>l</strong>ong</td></tr>
<tr><td>/m/</td><td>/m/</td><td><strong>m</strong>at</td></tr>
<tr><td>/n/</td><td>/n/</td><td><strong>n</strong>o</td></tr>
<tr><td>/oU/</td><td>/oʊ/</td><td>d<strong>oe</strong></td>
</tr><tr><td>/p/</td><td>/p/</td><td><strong>p</strong>ile</td></tr>
<tr><td>/r/</td><td>/r/</td><td><strong>r</strong>ed</td></tr>
<tr><td>/s/</td><td>/s/</td><td><strong>s</strong>ad</td></tr>
<tr><td>/t/</td><td>/t/</td><td><strong>t</strong>oad</td></tr>
<tr><td>/tS/</td><td>/tʃ/</td><td><strong>ch</strong>ild</td></tr>
<tr><td>/u/</td><td>/u/</td><td>n<strong>ew</strong></td></tr>
<tr><td>/v/</td><td>/v/</td><td><strong>v</strong>ase</td></tr>
<tr><td>/w/</td><td>/w/</td><td><strong>w</strong>onder</td></tr>
<tr><td>/z/</td><td>/z/</td><td><strong>z</strong>any</td></tr>
<tr><td>/{}/, /{/, /&amp;/</td><td>/æ/</td><td>h<strong>a</strong>t</td></tr>
</table>

There are some peculiarities worth noting here. First is the [cot-caught merger](https://en.wikipedia.org/wiki/Cot%E2%80%93caught_merger) that equates /ɑ/ and /ɔ/ along with other low back vowels. This admittedly reflects a bias towards the American West Coast and towards a younger demographic of singers. The exception to this merger is that /ɔr/ (horde) and /ɑr/ (hard) are distinct. If you enter /O/ or /A/ they will sound the same in OddVoices, but /Or/ and /Ar/ are different.

Second is the unification of /ə/ and /ʌ/. When sung, the English schwa is difficult to pin down and really represents a multitude of vowels. In varieties of North American English, /ə/ and /ʌ/ are closely linked and differ primarily by stress, so /ʌ/ is the best candidate for absorbing /ə/. Similarly, OddVoices doesn't distinguish /ɚ/ and /ɝ/. The CMU Pronouncing Dictionary unfortunately uses schwas a lot, so OddVoices enunciates a lot of words weirdly, like "im-uh-tate" for "imitate."

Finally, X-SAMPA's /{/ causes bracket matching issues in some text editors, so /{}/ and /&/ are provided as alternatives. The latter is borrowed from the so-called [Conlang X-SAMPA](https://www.vulgarlang.com/ipa-x-sampa-cxs-converter/) or CXS.

## MIDI file input

Type-0, type-1, and type-2 MIDI files are all supported. If a type-1 or type-2 file is supplied, only track 1 is used.

OddVoices takes all the MIDI lyric events and concatenates them together (with spaces in between) to produce the text to be sung. You do NOT need to make a lyric event for every word or syllable, and you don't need to align the lyric events with the notes at all. OddVoices will do this for you by counting syllables in the text.

Each syllable in the text is mapped to one note, unless notes overlap by a nonzero amount of time, in which case a melisma is created (multiple notes per syllable).

## How do I make a MIDI file with lyrics?

Out of software I have tried, [REAPER](https://www.reaper.fm/)'s built-in MIDI editor seems to be the best option. To add lyrics, select "Text events" in the dropdown in the lower left. Right click on the bottom panel to create a text event. In the Type dropdown, select "Lyrics." You can enter up to 127 characters of text in a lyric event.

Alternatively, go to File -> Lyrics -> Import track lyrics and follow the instructions to load up a .txt file.

It is recommended not to use File -> Export to new MIDI file... in the MIDI editor, since this export does not contain tempo or time signature information. Instead, go to the main window and click on File -> Export project MIDI... and check "Embed project tempo/time signature changes."

## JSON file input

As an alternative to MIDI file input, a bespoke JSON input format is also available for entering notes. There are several reasons to use this in place of a MIDI file. Some languages such as Python lack well-supported libraries for outputting MIDI files. Additionally, the JSON file format has features that are not currently supported in the MIDI file format, such as controlling formant shift and vibrato and using pitches that do not conform to 12EDO.

See `examples/example.json` for a demonstration of all available features in the JSON format.

## Semi-real-time vs. true real-time operation

Unlike most singing synthesizers, OddVoices is capable of operating in real time. However, this comes with tradeoffs.

Consider two half notes with lyrics like "rice cake." Ideally, the /s/ at the end of "rice" should come before the /k/ on the third beat. But a perfectly real-time singer doesn't know when the second note comes until right on the third beat! Real singers have to predict the future a little bit in order for timing to be natural and correct.

The command-line interface to OddVoices makes a compromise. It is a "semi-real-time" system where every time a note on is sent, it is accompanied by a "duration" argument that states the length of the syllable (if there are multiple notes forming a melisma, then the total melisma length must be supplied). This is achieved by looking ahead in the MIDI file, and allows the synthesizer to predict the timing of final consonant clusters in syllables.

If no duration is supplied, OddVoices operates in "true real-time" mode, and note off messages trigger final consonant clusters. This means that every note has to be manually shortened by some amount, or the lyrics will drift and misalign from the notes. You'll also have to adjust phoneme speed for best results.

