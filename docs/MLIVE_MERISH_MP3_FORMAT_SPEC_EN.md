# M-Live / Merish Karaoke MP3 Profile

MTA Audio Editor exports a standard MP3 with an ID3v2.3 tag. Lyrics are stored in SYLT content type 1 with a USLT fallback, chords in SYLT content type 5, and markers in SYLT content type 4. SYLT timestamps are expressed in milliseconds. Title, artist and authors are stored in TIT2, TPE1 and TCOM.

The profile keeps the MP3 audio stream independent from karaoke metadata. The generated PDF at `app/docs/MTA-Audio-Editor-M-Live-Merish-MP3-Format-Specification-EN.pdf` is the complete specification of the implemented profile.
