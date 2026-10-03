#!/usr/bin/env python3
from pathlib import Path
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "app" / "docs"
STATIC = ROOT / "app" / "static"
VERSION = (ROOT / "VERSION").read_text().strip()
BUILD = (ROOT / "BUILD_INFO").read_text().strip()
CREATOR = "Alessandro De Salvo <braket71@gmail.com>"
REPO = "https://github.com/desalvo/mta-audio-editor"
EXTRA = """
<style>
@page { size: A4; margin: 18mm 15mm 18mm 15mm; @bottom-center { content: "MTA Audio Editor - " counter(page) " / " counter(pages); color:#657487; font-size:9pt; } }
body { background:white; }
.wrap { box-shadow:none; max-width:none; padding:0; min-height:0; }
a.download { display:none; }
header,h2,h3 { break-after:avoid; }
table,.figure,pre,.note,.good,.danger { break-inside:avoid; }
</style>
"""
assets = {
    "/static/logo.svg": STATIC / "logo.svg",
    "/static/docs-assets/doc.css": STATIC / "docs-assets" / "doc.css",
    "/static/docs-assets/daw-overview.png": STATIC / "docs-assets" / "daw-overview.png",
    "/static/docs-assets/architecture.svg": STATIC / "docs-assets" / "architecture.svg",
    "/static/docs-assets/edit-workflow.svg": STATIC / "docs-assets" / "edit-workflow.svg",
    "/static/docs-assets/ci-pipeline.svg": STATIC / "docs-assets" / "ci-pipeline.svg",
}
for src_name, out_name in [("user.html", "MTA-Audio-Editor-User-Manual.pdf"), ("admin.html", "MTA-Audio-Editor-Administrator-Manual.pdf")]:
    text = (DOCS / src_name).read_text(encoding="utf-8")
    for token, path in assets.items():
        text = text.replace(token, path.as_uri())
    text = text.replace("__VERSION__", VERSION).replace("__BUILD__", BUILD).replace("__CREATOR__", CREATOR).replace("__REPOSITORY__", REPO)
    text = text.replace("</head>", EXTRA + "</head>")
    HTML(string=text, base_url=str(ROOT)).write_pdf(DOCS / out_name)
    print(DOCS / out_name)
