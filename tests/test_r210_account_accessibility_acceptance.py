"""Axe WCAG A/AA checks on actual complete owner pages with all details open.

Requires the supplied test-only axe source. No download or browser binary is
added to the production application; full product/native conformance is separate.
"""
import json
import os
from pathlib import Path

import pytest
from app import auth
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_credit_checkout import prepare
from test_r210_noncommercial_collection_e2e import nc_env as nc_env,enable  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_account_acceptance import configure,client,serve,assert_accessible_owner_page


@pytest.mark.parametrize('regime',['commercial','nc'])
@pytest.mark.parametrize('path',['/account','/account/credits'])
@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_actual_owner_pages_wcag_axe_and_named_keyboard_surfaces(request,monkeypatch,nc_browser_config,regime,path,language,width,tmp_path):
    from playwright.sync_api import sync_playwright
    if regime=='nc':
        env=request.getfixturevalue('nc_env');uid=env[1];enable(env)
        with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,uid))
    else:
        uid=request.getfixturevalue('account');request.getfixturevalue('provider');configure(uid,'no_plan',language);prepare(uid,monkeypatch)
    supplied=os.environ.get('MTA_TEST_AXE_CORE')
    if not supplied:pytest.skip('Supply test-only axe-core for actual owner accessibility acceptance; absence is not a pass')
    assert Path(supplied).is_file(),'Configured test-only axe-core path is absent'
    web=client(uid,monkeypatch);calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000},locale='en-GB')
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls));page.goto('https://mta.test'+path)
        page.locator('[data-owner-payments] button').first.wait_for();page.locator('[data-refund-content] p').first.wait_for()
        if path=='/account':
            page.locator('[data-account-financial]').wait_for()
            page.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
            page.locator('.ai-resource-panel [data-rows] tr').first.wait_for()
        else:page.locator('[data-credit-content] p').first.wait_for()
        page.add_script_tag(path=supplied)
        result=page.evaluate("async()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']},resultTypes:['violations','incomplete']})")
        report=Path(__file__).resolve().parents[1]/'docs/validation/r210/account-axe';report.mkdir(exist_ok=True)
        assert result['violations']==[],[(v['id'],v['impact'],[n['target'] for n in v['nodes']]) for v in result['violations']]
        # Clipped table text still has a concrete foreground/background. Verify
        # its contrast independently; gradients/opacity/unknown checks fail.
        reviews=[]
        for rule in result['incomplete']:
            assert rule['id']=='color-contrast',rule['id']
            for n in rule['nodes']:
                assert all(x.get('data',{}).get('messageKey')=='elmPartiallyObscured' for x in n['any']),n
                measured=page.locator(n['target'][0]).evaluate('''el=>{
                  const rgba=s=>{const a=s.match(/[\\d.]+/g)?.map(Number);if(!a||a.length<3)throw Error('Unknown color');return [...a.slice(0,3),a[3]??1]};
                  const fg=rgba(getComputedStyle(el).color);let bg=null;
                  for(let p=el;p;p=p.parentElement){const c=getComputedStyle(p);if(Number(c.opacity)!==1||c.backgroundImage!=='none')throw Error('Unreviewed compositing');const color=rgba(c.backgroundColor);if(color[3]===1){bg=color;break;}if(color[3]!==0)throw Error('Unreviewed alpha background');}
                  if(!bg||fg[3]!==1)throw Error('Unreviewed color');
                  const lum=a=>a.slice(0,3).map(x=>x/255).map(x=>x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
                  const a=lum(fg),b=lum(bg),c=getComputedStyle(el),large=parseFloat(c.fontSize)>=24||(parseFloat(c.fontSize)>=18.666&&Number(c.fontWeight)>=700);
                  return {foreground:fg,background:bg,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),minimum:large?3:4.5};
                }''')
                assert measured['ratio']>=measured['minimum'],(n['target'],measured)
                reviews.append({'target':n['target'],'reason':'clipped table text; opaque computed contrast verified',**measured})
        result['supplemental_review']={'unresolved':0,'computed_contrast':reviews,'scope':'Only opaque clipped table text; no rule exclusions or suppressed checks.'}
        # Every horizontally overflowing region can be reached and moved with
        # the keyboard, including engines that need explicit tabindex.
        for region in page.locator('[role=region][tabindex="0"]').all():
            if region.is_visible() and region.evaluate('e=>e.scrollWidth>e.clientWidth+2'):
                region.evaluate('e=>e.scrollLeft=0')
                region.focus();page.keyboard.press('ArrowRight')
                page.wait_for_function('e=>e.scrollLeft>0',arg=region.element_handle())
                assert region.evaluate("e=>getComputedStyle(e).outlineStyle!=='none'")
        (report/f'{regime}-{path.rsplit("/",1)[-1]}-{language}-{width}.json').write_text(json.dumps(result,indent=2)+'\n')
        assert_accessible_owner_page(page);assert not errors
        assert not any(method=='POST' for method,_,_ in calls)
        browser.close()
