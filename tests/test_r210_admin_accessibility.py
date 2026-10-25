"""Full E6 matrix: three shipped admin pages, nine tabs, two regimes/locales/themes/widths.

Real assets/private FastAPI/SQLite; provider transport alone is an isolated fake.
Axe is supplied test-only; missing tools cannot be counted as acceptance.
"""
import json
import os
from pathlib import Path

import pytest
from app import auth,paypal_payments as paypal
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_account_acceptance import client,serve

ROOT=Path(__file__).resolve().parents[1]
TABS=['web','storage','models','aiQueue','diagnostics','users','smtp','subscriptions','legal']


def setup(account,monkeypatch,regime,language):
    plan(account)
    order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'admin-accessibility-setup'})
    paypal.capture(account,order['order_id'])
    admin=auth.find_user('admin')['id']
    with auth.db() as c:
        c.execute('UPDATE users SET language=? WHERE id=?',(language,admin))
        if regime=='nc':c.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")
    if regime=='nc':(auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'NON_COMMERCIAL','revision':0}))
    return client(admin,monkeypatch)


def scan(page,name):
    result=page.evaluate("async()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']},resultTypes:['violations','incomplete']})")
    assert result['violations']==[],[(x['id'],[n['target'] for n in x['nodes']]) for x in result['violations']]
    contrast=[];empty=[]
    for rule in result['incomplete']:
        if rule['id']=='th-has-data-cells':
            for node in rule['nodes']:
                table=page.locator(node['target'][0]);assert '<td' not in node['html']
                assert table.locator('th').count()>0
                empty.append({'target':node['target'],'review':'Header-only empty dataset; no data cells to associate. No header hidden or disabled.'})
            continue
        assert rule['id']=='color-contrast',rule['id']
        for node in rule['nodes']:
            assert all(x.get('data',{}).get('messageKey') in {'elmPartiallyObscured','elmPartiallyObscuring'} for x in node['any']),node
            contrast.append(node['target'][0])
    measured=page.evaluate('''selectors=>selectors.map(selector=>{
      const el=document.querySelector(selector);if(!el)throw Error('Missing contrast target');
      const rgba=s=>{const a=s.match(/[\\d.]+/g)?.map(Number);if(!a||a.length<3)throw Error('Unknown color');return [...a.slice(0,3),a[3]??1]};
      const c=getComputedStyle(el),fg=rgba(c.color);let bg=null;
      for(let p=el;p;p=p.parentElement){const s=getComputedStyle(p);if(Number(s.opacity)!==1||s.backgroundImage!=='none')throw Error('Unreviewed compositing');const a=rgba(s.backgroundColor);if(a[3]===1){bg=a;break}if(a[3]!==0)throw Error('Unreviewed alpha')}
      if(!bg||fg[3]!==1)throw Error('Unreviewed color');
      const lum=a=>a.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
      const a=lum(fg),b=lum(bg),large=parseFloat(c.fontSize)>=24||(parseFloat(c.fontSize)>=18.666&&Number(c.fontWeight)>=700);
      return {selector,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),minimum:large?3:4.5,foreground:fg,background:bg};
    })''',contrast)
    assert all(x['ratio']>=x['minimum'] for x in measured),[x for x in measured if x['ratio']<x['minimum']]
    result['supplemental_review']={'unresolved':0,'opaque_clipped_text_contrast':measured,'empty_header_association':empty,'scope':'No rule exclusions. Only opaque clipped/overlaid text and header-only empty data reviewed; gradients, alpha and unknown checks reject acceptance.'}
    # Full document names/duplicate identities and viewport containment.
    duplicates=page.locator('[id]').evaluate_all('els=>els.map(e=>e.id).filter((id,i,a)=>a.indexOf(id)!==i)');assert duplicates==[]
    assert page.locator('main').count()==1 and page.locator('h1:visible').count()==1
    missing=page.locator('input:not([type=hidden]),select,textarea').evaluate_all("els=>els.filter(e=>e.getClientRects().length&&!e.disabled&&!(e.labels?.length||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby'))).map(e=>e.outerHTML)");assert missing==[]
    assert page.locator('img:not([alt])').count()==0
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),name
    folder=ROOT/'docs/validation/r210/admin-axe';folder.mkdir(exist_ok=True);(folder/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    # Every actually overflowing named region can be reached and moved.
    for region in page.locator('[role=region][tabindex="0"]').all():
        if region.is_visible() and region.evaluate('e=>e.scrollWidth>e.clientWidth+2'):
            region.evaluate('e=>e.scrollLeft=0');region.focus();page.keyboard.press('ArrowRight')
            page.wait_for_function('e=>e.scrollLeft>0',arg=region.element_handle())
            assert region.evaluate("e=>getComputedStyle(e).outlineStyle!=='none'")


@pytest.mark.parametrize('regime',['commercial','nc'])
@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
@pytest.mark.parametrize('theme',['light','dark'])
def test_entire_administration_axe_keyboard_responsive(account,provider,monkeypatch,nc_browser_config,regime,language,width,theme):
    from playwright.sync_api import sync_playwright
    supplied=os.environ.get('MTA_TEST_AXE_CORE')
    if not supplied:pytest.skip('Supply test-only axe-core; missing prerequisite is not acceptance')
    assert Path(supplied).is_file()
    web=setup(account,monkeypatch,regime,language);calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000},color_scheme=theme,locale='it-IT' if language=='it' else 'en-GB')
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls));page.goto('https://mta.test/settings');page.wait_for_load_state('networkidle');page.add_script_tag(path=supplied)
        assert page.locator('html').get_attribute('lang')==language
        for tab in TABS:
            page.locator('[data-tab="'+tab+'"]').click();page.wait_for_load_state('networkidle')
            if tab=='subscriptions' and regime=='commercial':page.locator('[data-paypal-save]').wait_for(state='attached')
            page.evaluate("document.querySelectorAll('details').forEach(d=>{if(d.getClientRects().length)d.open=true})")
            assert page.locator('[data-tab="'+tab+'"]').get_attribute('aria-selected')=='true'
            scan(page,f'{regime}-{language}-{width}-{theme}-{tab}')
        # Tablist has exactly one Tab stop and keyboard changes the real page.
        page.locator('[data-tab=legal]').focus();page.keyboard.press('Home');assert page.locator('[data-tab=web]').evaluate('e=>e===document.activeElement')
        page.keyboard.press('ArrowRight');assert page.locator('#storageTab').is_visible()
        assert page.locator('[role=tab][tabindex="0"]').count()==1
        # Inline optional plugin catalogue: no install/build/download is invoked.
        page.locator('[data-tab=web]').click();page.locator('[data-optional-vst3] > button').click();page.wait_for_load_state('networkidle')
        scan(page,f'{regime}-{language}-{width}-{theme}-optional-plugins')
        for name in ['ai-billing','ai-tokens']:
            page.goto('https://mta.test/admin/'+name);page.wait_for_load_state('networkidle');page.add_script_tag(path=supplied);page.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
            scan(page,f'{regime}-{language}-{width}-{theme}-{name}')
        # Persistent non-modal job monitor supports focus, keyboard close/return.
        page.locator('#aj-launch').focus();page.keyboard.press('Enter');page.locator('#aj-panel').wait_for();page.wait_for_load_state('networkidle')
        page.wait_for_function("expected=>document.querySelector('#aj-close').getAttribute('aria-label')===expected",arg='Chiudi lista job' if language=='it' else 'Close job list')
        assert page.locator('#aj-close').evaluate('e=>e===document.activeElement')
        scan(page,f'{regime}-{language}-{width}-{theme}-job-monitor')
        page.keyboard.press('Escape');assert page.locator('#aj-panel').is_hidden() and page.locator('#aj-launch').evaluate('e=>e===document.activeElement')
        assert not errors,errors
        assert not any(method!='GET' for method,_,_ in calls),calls
        assert not any(status>=500 for _,_,status in calls)
        browser.close()
