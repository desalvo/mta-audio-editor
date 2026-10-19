"""Build the shipped VST3 manuals with the approved existing full-page covers."""
from pathlib import Path
import html
import re
from weasyprint import HTML

ROOT=Path(__file__).resolve().parents[1]


def body(markdown):
    blocks=[]
    for part in markdown.split('\n\n'):
        part=part.strip()
        if not part:continue
        match=re.match(r'^(#{1,3}) (.*)$',part)
        if match:
            n=len(match[1]);blocks.append(f'<h{n}>'+html.escape(match[2])+f'</h{n}>')
        else:blocks.append('<p>'+html.escape(part.replace('\n',' '))+'</p>')
    return '\n'.join(blocks)


def build():
    for lang in ('IT','EN'):
        cover=(ROOT/'app/static/docs-assets'/('cover-user-'+lang.lower()+'.png')).as_uri()
        label='Manuale VST3' if lang=='IT' else 'VST3 Manual'
        build_id=(ROOT/'BUILD_INFO').read_text().strip()
        text=(ROOT/'docs'/('VST3_USER_GUIDE_'+lang+'.md')).read_text()
        document='''<!doctype html><html lang="'''+lang.lower()+'''"><head><meta charset="utf-8"><style>
        @page {size:A4;margin:18mm 17mm;@bottom-center {content:"MTA Audio Editor 0.3.0-r210 | " counter(page);font-size:8pt;color:#54667a}}
        @page cover {margin:0;@bottom-center{content:none}}
        body {margin:0;font-family:DejaVu Sans,sans-serif;font-size:9.5pt;line-height:1.35;color:#243247}
        .cover {position:relative;page:cover;width:210mm;height:297mm;break-after:page;background:url("'''+cover+'''") center/210mm 297mm no-repeat}
        .cover-title{position:absolute;top:22.8%;left:6%;right:6%;height:9%;box-sizing:border-box;padding:3mm;background:#374357;color:white;border:1px solid #71d0ff;border-radius:3mm;font-size:18pt;font-weight:bold}
        .cover-meta{position:absolute;top:48.2%;left:3%;width:59%;height:21%;box-sizing:border-box;padding:4mm;background:#1c2937;color:white;border:1px solid #a0bdcf;border-radius:3mm;font-size:9pt;line-height:1.7}
        h1{font-size:18pt;color:#143d65}h2{font-size:13pt;color:#1c5380;margin-top:5mm;break-after:avoid}p{margin:.55em 0;orphans:3;widows:3}
        </style></head><body><div class="cover"><div class="cover-title">'''+label+'''</div><div class="cover-meta">MTA Audio Editor<br>0.3.0-r210<br>Build: '''+html.escape(build_id)+'''<br>Alessandro De Salvo<br>License: EUPL-1.2</div></div>'''+body(text)+'''</body></html>'''
        target=ROOT/'app/docs'/('MTA-Audio-Editor-VST3-Manual-'+lang+'.pdf');HTML(string=document,base_url=str(ROOT)).write_pdf(target)
        print(target)


if __name__=='__main__':build()
