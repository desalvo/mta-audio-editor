"""Instance-wide IT/EN localization with per-account preferences and safe HTML text."""
from contextvars import ContextVar
from functools import lru_cache
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

current_language = ContextVar('mta_language', default='en')
LANGUAGES = frozenset(('auto','it','en'))


def browser_language(header):
    choices=[]
    for index,part in enumerate(str(header or '').split(',')):
        fields=part.strip().lower().split(';');name=fields[0].split('-')[0]
        try:q=next((float(x.strip()[2:]) for x in fields[1:] if x.strip().startswith('q=')),1.0)
        except ValueError:continue
        if name in ('it','en') and 0<q<=1:choices.append((-q,index,name))
    return min(choices)[2] if choices else 'en'


def effective(choice='auto', browser='en'):
    return choice if choice in ('it','en') else browser_language(browser)


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('i18n_catalog.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=2)
def mapping(language):
    pairs=catalog()
    if language=='it':return pairs
    return {**{it:en for en,it in pairs.items()},**{'Estrai lyrics': 'Extract lyrics', 'Estrai chords': 'Extract chords', 'Estrai marker': 'Extract markers', 'Avanzamento': 'Progress', 'Da (UTC)': 'From (UTC)', 'Path di salvataggio': 'Save path', 'Precedenti': 'Previous'}}


@lru_cache(maxsize=2)
def patterns(language):
    result=[]
    for pattern,replacement in mapping(language).items():
        if '{0}' not in pattern:continue
        parts=re.split(r'(\{\d+\})',pattern)
        slots=[int(x[1:-1]) for x in parts if re.fullmatch(r'\{\d+\}',x)]
        regex=''.join('(.*?)' if re.fullmatch(r'\{\d+\}',part) else re.escape(part) for part in parts)
        result.append((re.compile(regex,re.S),slots,replacement))
    return result


def translate(value,language=None):
    raw=str(value or '');language=language or current_language.get();core=raw.strip()
    if not core:return raw
    table=mapping(language);translated=table.get(core)
    if translated is None:
        for regex,slots,replacement in patterns(language):
            match=regex.fullmatch(core)
            if match:
                data=dict(zip(slots,match.groups()))
                translated=re.sub(r'\{(\d+)\}',lambda m:data.get(int(m[1]),m[0]),replacement);break
    if translated is None:
        # Compose UI fragments without translating captured names or content.
        for separator in (' · ','\n'):
            if separator in core:
                parts=core.split(separator);converted=[translate(p,language) for p in parts]
                if converted!=parts:translated=separator.join(converted);break
    if translated is None:
        match=re.fullmatch(r'(.+?)(:\s*|\s+)([\d~−+].*)',core)
        if match and match[1] in table:translated=table[match[1]]+match[2]+match[3]
    if translated is None:
        match=re.fullmatch(r'([^A-Za-zÀ-ÿ0-9]+)([A-Za-zÀ-ÿ].*)',core)
        if match:
            body=translate(match[2],language)
            if body!=match[2]:translated=match[1]+body
    if translated is None:
        match=re.fullmatch(r'([^:\n]+):(\s+)(.*)',core,flags=re.S)
        if match and match[1] in table:translated=table[match[1]]+':'+match[2]+match[3]
    if translated is None:
        parenthetical=re.sub(r'\(([^()]*)\)',lambda m:'('+translate(m[1],language)+')',core)
        if parenthetical!=core:translated=parenthetical
    if translated is None:return raw
    return raw[:len(raw)-len(raw.lstrip())]+translated+raw[len(raw.rstrip()):]


class _LocalizeHTML(HTMLParser):
    def __init__(self,language):
        super().__init__(convert_charrefs=False);self.language=language;self.output=[];self.stack=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);text=self.get_starttag_text()
        protected=(self.stack and self.stack[-1][1]) or tag in ('script','style','code','pre','textarea') or attrs.get('translate')=='no' or 'data-i18n-preserve' in attrs or 'data-track-name' in attrs or bool(set(attrs.get('class','').split()) & {'channel-name','track-name','meta-value','lyric-word'})
        for key in ('title','aria-label','placeholder'):
            if key in attrs and not protected:
                original=attrs[key];changed=translate(original,self.language)
                if changed!=original:
                    text=re.sub(r'('+re.escape(key)+r'\s*=\s*)([\'"])(.*?)\2',lambda m:m[1]+m[2]+escape(changed,quote=True)+m[2],text,count=1,flags=re.I|re.S)
        if tag=='html':text=re.sub(r'\blang\s*=\s*([\'"]).*?\1','lang="'+self.language+'"',text,count=1)
        self.output.append(text)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append((tag,protected))
    def handle_startendtag(self,tag,attrs):
        depth=len(self.stack);self.handle_starttag(tag,attrs);del self.stack[depth:]
    def handle_endtag(self,tag):
        self.output.append('</'+tag+'>')
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:del self.stack[i:];break
    def handle_data(self,data):self.output.append(data if self.stack and self.stack[-1][1] else translate(data,self.language))
    def handle_entityref(self,name):self.output.append('&'+name+';')
    def handle_charref(self,name):self.output.append('&#'+name+';')
    def handle_decl(self,decl):self.output.append('<!'+decl+'>')
    def handle_comment(self,data):self.output.append('<!--'+data+'-->')


def translate_html(text,language=None):
    parser=_LocalizeHTML(language or current_language.get());parser.feed(text);parser.close();return ''.join(parser.output)


def inject_runtime(text,language,choice='auto'):
    if '/static/localization.js' in text:return text
    setup=json.dumps({'language':language,'choice':choice},separators=(',',':'))
    scripts='<script>window.MTA_LOCALE='+setup+'</script><script src="/static/i18n_catalog.js?v=0.3.0-r210-decimal-zoom-accounted"></script><script src="/static/localization.js?v=0.3.0-r210-decimal-zoom-accounted"></script>'
    return text.replace('</head>',scripts+'</head>',1) if '</head>' in text else scripts+text


async def localize_response(response,language,choice='auto'):
    if 'text/html' not in response.headers.get('content-type','') or int(response.headers.get('content-length','0') or 0)>2_000_000:return response
    chunks=[chunk async for chunk in response.body_iterator];data=b''.join(chunks).decode('utf-8')
    data=inject_runtime(translate_html(data,language),language,choice).encode('utf-8')
    async def body():yield data
    response.body_iterator=body();response.headers['Content-Length']=str(len(data));response.headers['Content-Language']=language
    response.headers['Vary']=', '.join(dict.fromkeys([x.strip() for x in response.headers.get('Vary','').split(',') if x.strip()]+['Accept-Language','Cookie']))
    return response


def user_language(user_id):
    from . import auth
    row=auth.get_user(user_id)
    if not row:return current_language.get()
    data=dict(row)
    return effective(data.get('language','auto'),data.get('browser_language','en'))


def recipient_language(email):
    from . import auth
    with auth.db() as con:row=con.execute('SELECT language,browser_language FROM users WHERE email=? COLLATE NOCASE',(email,)).fetchone()
    return effective(row['language'],row['browser_language']) if row else current_language.get()
