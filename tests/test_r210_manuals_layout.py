"""Keep online/PDF references together instead of appending unstyled chapters."""
from pathlib import Path
from html.parser import HTMLParser
import re

import pytest

ROOT=Path(__file__).resolve().parents[1]


class Manual(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.images=[];self.stack=[];self.headings_outside=[]
    def handle_starttag(self,tag,attributes):
        attrs=dict(attributes)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='img':self.images.append(attrs['src'])
        if tag=='h2' and not any('wrap' in c.split() for t,c in self.stack):self.headings_outside.append(attrs.get('id'))
        if tag not in {'meta','link','img','br','hr','input','source'}:self.stack.append((tag,attrs.get('class','')))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break


@pytest.mark.parametrize('name',['user','user-en','admin','admin-en','vst3-it','vst3-en'])
def test_manual_structure_and_assets(name):
    text=(ROOT/'app/docs'/f'{name}.html').read_text();doc=Manual();doc.feed(text)
    assert not doc.headings_outside
    assert len(doc.ids)==len(set(doc.ids))
    assert 'technical-appendix' in doc.ids
    assert len(doc.images)>=3
    assert 'file:///' not in text
    for src in doc.images:
        assert src.startswith('/static/')
        assert (ROOT/'app'/src.lstrip('/').split('?')[0]).is_file(),src
    for target in re.findall(r'href="#([^"]+)"',text):assert target in doc.ids


@pytest.mark.parametrize('role',['User','Administrator','VST3'])
@pytest.mark.parametrize('language',['IT','EN'])
def test_shipped_pdf_has_current_version_and_complete_reference(role,language):
    fitz=pytest.importorskip('pymupdf')
    with fitz.open(ROOT/'app/docs'/f'MTA-Audio-Editor-{role}-Manual-{language}.pdf') as pdf:
        assert '0.3.0-r210' in pdf[0].get_text()
        text=' '.join(p.get_text() for p in pdf)
        assert ('Appendici tecniche' if language=='IT' else 'Technical appendices') in text
        assert '256 MiB' in text
        assert '0.35' in text or '0,35' in text
        for page in list(pdf)[1:]:
            for block in page.get_text('blocks'):
                if len(block)>4 and block[4].strip():
                    assert block[0]>=15 and block[2]<=page.rect.width-15
