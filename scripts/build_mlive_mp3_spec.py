#!/usr/bin/env python3
from pathlib import Path
from html import escape
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "app" / "docs"
SRC = ROOT / "docs"
VERSION = (ROOT / "VERSION").read_text().strip()
REVISION = (ROOT / "REVISION").read_text().strip()
BUILD = (ROOT / "BUILD_INFO").read_text().strip()

CSS = r"""
@page { size:A4; margin:17mm 16mm 18mm 16mm; @bottom-center { content:"MTA Audio Editor - " counter(page) " / " counter(pages); color:#667788; font-size:8pt; } }
@page cover { size:A4; margin:0; @bottom-center { content:none; } }
body { font-family: Arial, sans-serif; color:#16202a; font-size:10.3pt; line-height:1.42; }
h1 { color:#0d3b66; font-size:23pt; margin:0 0 4mm; }
h2 { color:#155d8a; font-size:15pt; border-bottom:1px solid #c8d7e3; padding-bottom:2mm; margin-top:8mm; break-after:avoid; }
h3 { color:#204a68; font-size:11.5pt; margin-top:5mm; break-after:avoid; }
p,li { orphans:3; widows:3; }
table { width:100%; border-collapse:collapse; margin:3mm 0 5mm; break-inside:avoid; font-size:9.2pt; }
th,td { border:1px solid #c9d4dc; padding:2.2mm; vertical-align:top; }
th { background:#eaf2f8; text-align:left; }
code { font-family:DejaVu Sans Mono, monospace; font-size:8.7pt; background:#f2f5f7; padding:0.2mm 0.6mm; }
pre { background:#f5f7f9; border:1px solid #d8e0e6; padding:3mm; font-family:DejaVu Sans Mono, monospace; font-size:8.4pt; white-space:pre-wrap; break-inside:avoid; }
.note { border-left:4px solid #2385b8; background:#eef8fc; padding:3mm 4mm; margin:4mm 0; }
.warn { border-left-color:#c98516; background:#fff8e8; }
.meta { color:#5c6b75; font-size:9pt; margin-bottom:8mm; }
ul { padding-left:6mm; }
.cover-page { page:cover; width:210mm; height:297mm; break-after:page; position:relative; color:white; overflow:hidden; background:#020817 center/210mm 297mm no-repeat; }
.cover-title { position:absolute; left:12mm; right:12mm; top:65mm; background:rgba(3,18,45,.92); border:1.4px solid #4fdcff; border-radius:5mm; padding:5mm 6mm; }
.cover-title h1 { color:#fff; margin:0 0 1.6mm; font-size:18pt; line-height:1.18; }
.cover-title p { color:#d9efff; margin:0; font-size:10.5pt; }
.cover-meta { position:absolute; left:6mm; top:140mm; width:113mm; border:1px solid rgba(255,255,255,.92); border-radius:4mm; background:rgba(2,12,30,.72); padding:4mm; font-size:8.7pt; line-height:1.45; }
"""

SPECS = {
"IT": {
"title":"Profilo MP3 Karaoke M-Live / Merish - Specifica di interoperabilita",
"outfile":"MTA-Audio-Editor-M-Live-Merish-MP3-Format-Specification-IT.pdf",
"sections":[
("Scopo", "Il profilo produce un normale file MP3 stereo con metadati ID3v2.3 sincronizzati per testo, accordi e marker. Il file resta riproducibile dai player MP3 generici e aggiunge informazioni karaoke destinate ai dispositivi M-Live/Merish e ad altri lettori compatibili ID3/SYLT."),
("Compatibilita di riferimento", "I dispositivi Merish dichiarano la lettura di MP3 con testo ID3/SYLT e la gestione di testo, accordi e marker sugli MP3. Il profilo di MTA Audio Editor usa quindi primitive ID3 standard e mantiene l'audio MP3 indipendente dai metadati karaoke."),
("Struttura del file", "L'output e composto da un tag ID3v2.3 all'inizio del file seguito dallo stream audio MPEG Layer III. Un eventuale tag ID3v2 precedente viene sostituito, non annidato. Lo stream audio non viene ricodificato durante l'inserimento dei metadati."),
("Frame ID3 utilizzati", "TABLE"),
("Sincronizzazione SYLT", "Ogni frame SYLT usa timestamp format 2, cioe millisecondi. Le lyrics usano content type 1, i marker content type 4 (eventi) e gli accordi content type 5 (chord). Le stringhe sono codificate ISO-8859-1 per massimizzare la compatibilita con hardware karaoke legacy; caratteri non rappresentabili vengono sostituiti in modo deterministico."),
("Lyrics", "Quando sono disponibili timestamp a livello di sillaba, vengono esportati quelli; altrimenti vengono usati i timestamp delle parole e, come fallback, quelli delle righe. La fine della riga e conservata con un newline sull'ultimo token sincronizzato. Viene scritto anche USLT con il testo completo non sincronizzato."),
("Accordi", "Gli accordi attivi vengono ordinati per timestamp e scritti in un SYLT separato con content type chord. Gli accordi eliminati o esclusi non vengono esportati. Il nome dell'accordo e conservato come testo del cue sincronizzato."),
("Marker", "I marker attivi vengono esportati come eventi sincronizzati in un SYLT separato. Marker eliminati o disabilitati non vengono inclusi."),
("Metadati descrittivi", "TIT2 contiene il titolo, TPE1 l'artista/interprete e TCOM gli autori/compositori quando disponibili. Un frame TXXX identifica il profilo di esportazione usato da MTA Audio Editor."),
("Parametri audio", "Il profilo usa lo stesso renderer MP3 dell'export standard. Sono selezionabili sample rate 44.1/48 kHz, bitrate 128/192/256/320 kbps e normalizzazione opzionale. Se il progetto lavora a 96 kHz, l'export MP3 viene ricampionato a 44.1 o 48 kHz secondo la scelta utente. I metadati karaoke vengono aggiunti dopo il render audio."),
("Validazione", "Un file conforme deve iniziare con ID3 versione 2.3, contenere almeno un SYLT lyrics quando il progetto ha testo sincronizzato e deve contenere SYLT content type 5 quando il progetto ha accordi. I timestamp devono essere monotoni all'interno di ciascun frame. Dopo il tag ID3 deve essere presente uno stream MP3 valido."),
("Limiti e interoperabilita", "Questo documento descrive il profilo generato da MTA Audio Editor e non e una specifica ufficiale del produttore. Firmware differenti possono applicare regole diverse alla visualizzazione di accordi, marker, caratteri estesi o colori. Per produzioni live si raccomanda una verifica sul modello e firmware di destinazione."),
]},
"EN": {
"title":"M-Live / Merish Karaoke MP3 Profile - Interoperability Specification",
"outfile":"MTA-Audio-Editor-M-Live-Merish-MP3-Format-Specification-EN.pdf",
"sections":[
("Purpose", "This profile produces a normal stereo MP3 file with synchronized ID3v2.3 metadata for lyrics, chords and markers. The file remains playable by generic MP3 players while adding karaoke information intended for M-Live/Merish devices and other ID3/SYLT-compatible readers."),
("Compatibility baseline", "Merish devices advertise MP3 lyric support through ID3/SYLT and provide editing/display of lyrics, chords and markers on MP3 backing tracks. MTA Audio Editor therefore uses standard ID3 primitives while keeping the MP3 audio stream independent from karaoke metadata."),
("File structure", "The output consists of an ID3v2.3 tag at the beginning of the file followed by the MPEG Layer III audio stream. Any previous ID3v2 tag is replaced rather than nested. The audio stream is not re-encoded while karaoke metadata is inserted."),
("ID3 frames", "TABLE"),
("SYLT synchronization", "Each SYLT frame uses timestamp format 2 (milliseconds). Lyrics use content type 1, markers use content type 4 (events), and chords use content type 5 (chord). Text uses ISO-8859-1 to maximize compatibility with legacy karaoke hardware; unsupported characters are replaced deterministically."),
("Lyrics", "When syllable timestamps are available they are exported; otherwise word timestamps are used, with line timestamps as the final fallback. A newline is appended to the last synchronized token of each line. A USLT frame is also written with the complete unsynchronized lyrics."),
("Chords", "Active chords are ordered by timestamp and stored in a dedicated SYLT frame using the chord content type. Deleted or excluded chords are not exported. The chord symbol is the synchronized cue text."),
("Markers", "Active markers are exported as synchronized events in a dedicated SYLT frame. Deleted or disabled markers are omitted."),
("Descriptive metadata", "TIT2 stores the title, TPE1 the performer/artist, and TCOM the authors/composers when available. A TXXX frame identifies the MTA Audio Editor export profile."),
("Audio parameters", "The profile uses the same MP3 renderer as normal project export. Sample rate 44.1/48 kHz, bitrate 128/192/256/320 kbps and optional normalization are available. A 96 kHz project is resampled to 44.1 or 48 kHz for MP3 export according to the selected output setting. Karaoke metadata is inserted after audio rendering."),
("Validation", "A conforming file starts with ID3 version 2.3, contains at least one lyrics SYLT when synchronized lyrics exist, and contains a SYLT content type 5 when chords exist. Timestamps must be monotonic within each frame. A valid MP3 audio stream follows the ID3 tag."),
("Limits and interoperability", "This document specifies the profile generated by MTA Audio Editor and is not an official manufacturer specification. Different firmware versions may apply different presentation rules for chords, markers, extended characters or colors. Live-production workflows should validate the output on the target model and firmware."),
]}}

TABLE_IT = [("Frame","Uso"),("TIT2","Titolo"),("TPE1","Artista / interprete"),("TCOM","Autori / compositori"),("USLT","Testo completo non sincronizzato"),("SYLT type 1","Lyrics sincronizzate"),("SYLT type 5","Accordi sincronizzati"),("SYLT type 4","Marker / eventi sincronizzati"),("TXXX","Identificazione del profilo")]
TABLE_EN = [("Frame","Purpose"),("TIT2","Title"),("TPE1","Artist / performer"),("TCOM","Authors / composers"),("USLT","Complete unsynchronized lyrics"),("SYLT type 1","Synchronized lyrics"),("SYLT type 5","Synchronized chords"),("SYLT type 4","Synchronized markers / events"),("TXXX","Profile identification")]

def table(rows):
    return '<table>' + ''.join('<tr>'+''.join(f'<th>{escape(c)}</th>' if i==0 else f'<td>{escape(c)}</td>' for c in row)+'</tr>' for i,row in enumerate(rows)) + '</table>'

for lang, spec in SPECS.items():
    bg_name = 'cover-base-it.png' if lang == 'IT' else 'cover-base-en.png'
    bg = (ROOT / 'app' / 'static' / 'docs-assets' / bg_name).as_uri()
    subtitle = 'Specifica tecnica del formato karaoke MP3' if lang == 'IT' else 'Karaoke MP3 format technical specification'
    cover = f'''<section class="cover-page" style="background-image:url({bg})"><div class="cover-title"><h1>{escape(spec["title"])}</h1><p>{escape(subtitle)}</p></div><div class="cover-meta"><b>Versione: {VERSION} · Revisione: {REVISION}</b><br><b>Build: {BUILD}</b><br><br>Alessandro De Salvo<br>braket71@gmail.com<br><br>github.com/desalvo/mta-audio-editor<br><br>Licenza: EUPL-1.2</div></section>'''
    body = [cover, f'<h1>{escape(spec["title"])}</h1>', f'<div class="meta">MTA Audio Editor {VERSION}-r{REVISION} - build {BUILD}</div>']
    for heading, value in spec['sections']:
        body.append(f'<h2>{escape(heading)}</h2>')
        if value == 'TABLE':
            body.append(table(TABLE_IT if lang == 'IT' else TABLE_EN))
        else:
            body.append(f'<p>{escape(value)}</p>')
    body.append('<h2>Binary layout / Layout binario</h2>')
    body.append('<pre>ID3v2.3 header\n  TIT2 / TPE1 / TCOM\n  USLT\n  SYLT (lyrics, type=1, ms)\n  SYLT (chords, type=5, ms)\n  SYLT (markers, type=4, ms)\n  TXXX profile id\nMPEG Layer III audio frames...</pre>')
    html = '<!doctype html><html><head><meta charset="utf-8"><style>'+CSS+'</style></head><body>'+''.join(body)+'</body></html>'
    out = DOCS / spec['outfile']
    HTML(string=html, base_url=str(ROOT)).write_pdf(out)
    print(out)
