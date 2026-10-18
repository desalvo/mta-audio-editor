#!/usr/bin/env python3
from pathlib import Path
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "app" / "docs"
STATIC = ROOT / "app" / "static"
VERSION = (ROOT / "VERSION").read_text().strip()
REVISION = (ROOT / "REVISION").read_text().strip()
BUILD = (ROOT / "BUILD_INFO").read_text().strip()
CREATOR = "Alessandro De Salvo &lt;braket71@gmail.com&gt;"
REPO = "https://github.com/desalvo/mta-audio-editor"

EXTRA = r"""
<style>
@page { size: A4; margin: 17mm 15mm 18mm 15mm; @bottom-center { content: "MTA Audio Editor - " counter(page) " / " counter(pages); color:#657487; font-size:8.5pt; } }
@page cover { size: A4; margin: 0; @bottom-center { content: none; } }
body { background:white; }
.wrap { box-shadow:none; max-width:none; padding:0; min-height:0; }
.cover { height:297mm; min-height:297mm; margin:0; padding:19mm 17mm; }
.cover-card { width:78%; }
.langbar { display:none; }
h1,h2,h3,h4 { break-after:avoid-page; page-break-after:avoid; }
h1 + p,h2 + p,h2 + .note,h2 + .figure,h2 + table,h3 + p,h3 + .note,h3 + .figure,h3 + table,h4 + p { break-before:avoid-page; page-break-before:avoid; }
table,.figure,pre,.note,.good,.warn,.danger,.example,.step { break-inside:avoid; page-break-inside:avoid; }
.toc { break-inside:avoid; }
</style>
"""
assets = {
    "/static/logo.svg": STATIC / "logo.svg",
    "/static/login-background.png": STATIC / "login-background.png",
    "/static/docs-assets/cover-daw-studio.png": STATIC / "docs-assets" / "cover-daw-studio.png",
    "/static/docs-assets/cover-user-it.png": STATIC / "docs-assets" / "cover-user-it.png",
    "/static/docs-assets/cover-user-en.png": STATIC / "docs-assets" / "cover-user-en.png",
    "/static/docs-assets/cover-admin-it.png": STATIC / "docs-assets" / "cover-admin-it.png",
    "/static/docs-assets/cover-admin-en.png": STATIC / "docs-assets" / "cover-admin-en.png",
    "/static/docs-assets/doc.css": STATIC / "docs-assets" / "doc.css",
    "/static/docs-assets/daw-overview.png": STATIC / "docs-assets" / "daw-overview.png",
    "/static/docs-assets/transport.png": STATIC / "docs-assets" / "transport.png",
    "/static/docs-assets/timeline.png": STATIC / "docs-assets" / "timeline.png",
    "/static/docs-assets/mixer.png": STATIC / "docs-assets" / "mixer.png",
    "/static/docs-assets/export-panel.png": STATIC / "docs-assets" / "export-panel.png",
    "/static/docs-assets/inspector.png": STATIC / "docs-assets" / "inspector.png",
    "/static/docs-assets/plugin-editor.png": STATIC / "docs-assets" / "plugin-editor.png",
    "/static/docs-assets/architecture.svg": STATIC / "docs-assets" / "architecture.svg",
    "/static/docs-assets/architecture.png": STATIC / "docs-assets" / "architecture.png",
    "/static/docs-assets/edit-workflow.svg": STATIC / "docs-assets" / "edit-workflow.svg",
    "/static/docs-assets/edit-workflow.png": STATIC / "docs-assets" / "edit-workflow.png",
    "/static/docs-assets/ci-pipeline.svg": STATIC / "docs-assets" / "ci-pipeline.svg",
    "/static/docs-assets/ci-pipeline.png": STATIC / "docs-assets" / "ci-pipeline.png",
    "/static/docs-assets/project-lifecycle.svg": STATIC / "docs-assets" / "project-lifecycle.svg",
    "/static/docs-assets/project-lifecycle.png": STATIC / "docs-assets" / "project-lifecycle.png",
    "/static/docs-assets/playback-sync.svg": STATIC / "docs-assets" / "playback-sync.svg",
    "/static/docs-assets/playback-sync.png": STATIC / "docs-assets" / "playback-sync.png",
    "/static/docs-assets/mobile-connection.svg": STATIC / "docs-assets" / "mobile-connection.svg",
    "/static/docs-assets/mobile-connection.png": STATIC / "docs-assets" / "mobile-connection.png",
    "/static/docs-assets/mta-layout.svg": STATIC / "docs-assets" / "mta-layout.svg",
    "/static/docs-assets/mta-layout.png": STATIC / "docs-assets" / "mta-layout.png",
    "/static/docs-assets/mta-profiles.svg": STATIC / "docs-assets" / "mta-profiles.svg",
    "/static/docs-assets/mta-profiles.png": STATIC / "docs-assets" / "mta-profiles.png",
}
outputs = [
    ("user.html", "MTA-Audio-Editor-User-Manual-IT.pdf"),
    ("user-en.html", "MTA-Audio-Editor-User-Manual-EN.pdf"),
    ("admin.html", "MTA-Audio-Editor-Administrator-Manual-IT.pdf"),
    ("admin-en.html", "MTA-Audio-Editor-Administrator-Manual-EN.pdf"),
]
cover_for_source = {
    "user.html": STATIC / "docs-assets" / "cover-user-it.png",
    "user-en.html": STATIC / "docs-assets" / "cover-user-en.png",
    "admin.html": STATIC / "docs-assets" / "cover-admin-it.png",
    "admin-en.html": STATIC / "docs-assets" / "cover-admin-en.png",
}

for src_name, out_name in outputs:
    text = (DOCS / src_name).read_text(encoding="utf-8")
    for token, path in assets.items():
        text = text.replace(token, path.as_uri())
    text = text.replace("__VERSION__", VERSION).replace("__REVISION__", REVISION).replace("__BUILD__", BUILD).replace("__CREATOR__", CREATOR).replace("__REPOSITORY__", REPO)
    cover_uri = cover_for_source[src_name].as_uri()
    # The web manual keeps its interactive cover section. For PDF output replace
    # that section with an isolated A4 page outside .wrap so no web layout rules
    # can resize, shift, or fragment the approved raster cover.
    import re
    text = re.sub(r'<section class="cover cover-fullpage">.*?</section>', '', text, count=1, flags=re.S)
    text = text.replace('<body><div class="wrap">', '<body><div class="pdf-cover"></div><div class="wrap">', 1)
    pdf_cover_css = (
        '<style>'
        '@page cover { size:A4; margin:0; @bottom-center { content:none; } }'
        '.pdf-cover { page:cover; width:210mm; height:297mm; min-height:297mm; margin:0; padding:0; '
        'break-after:page; page-break-after:always; background-image:url("' + cover_uri + '"); '
        'background-repeat:no-repeat; background-position:center center; background-size:210mm 297mm; position:relative; }'
        '</style>'
    )
    text = text.replace("</head>", EXTRA + pdf_cover_css + "</head>")
    HTML(string=text, base_url=str(ROOT)).write_pdf(DOCS / out_name)
    print(DOCS / out_name)


# Build the M-Live/Merish MP3 interoperability specification alongside the manuals.
import subprocess as _subprocess
_subprocess.run(["python", str(ROOT / "scripts" / "build_mlive_mp3_spec.py")], check=True)
