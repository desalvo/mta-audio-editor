'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag) { this.tagName=tag; this.children=[]; this.attrs={}; this.textContent=''; this.disabled=false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=[...nodes]; }
  setAttribute(k,v) { this.attrs[k]=v; }
  querySelectorAll(tag) { const all=[]; const visit=x=>{if(x.tagName===tag)all.push(x);for(const c of x.children)visit(c)};visit(this);return all; }
}
const root=new Element('section');let reads=0,posts=0;
const record=pending=>({id:'order',provider:'paypal',kind:'credits',status:'paid',amount_cents:500,created_at:1,
  financial_held_minor:500,financial_review_pending:pending,can_verify:true,checkout_url:null});
const context={document:{querySelector:()=>root,createElement:tag=>new Element(tag)},
  window:{MtaLocale:{language:'en'},addEventListener:()=>{},dispatchEvent:()=>{}},
  fetch:async(_url,opts)=>{if(opts.method==='POST'){posts++;return {ok:false}}reads++;return {ok:true,json:async()=>({items:[record(reads>1)],next_offset:null,commercial_payments:true})}},
  confirm:()=>true,Intl,Date,URL,CustomEvent:class{},console};
vm.runInNewContext(fs.readFileSync('app/static/owner_payments.js','utf8'),context);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await settle();
  const button=root.querySelectorAll('button').find(x=>x.textContent==='Verify status without collecting payment');
  assert.ok(button);await button.onclick();await settle();
  const all=[];const visit=x=>{all.push(x);x.children.forEach(visit)};visit(root);
  assert.equal(posts,1);assert.equal(reads,2);
  assert.ok(all.some(x=>x.textContent.includes('Unresolved financial evidence')));
  assert.ok(all.some(x=>x.textContent.includes('Payment funds held or reversed')));
  assert.ok(all.some(x=>x.textContent.includes('Payment history unavailable')));
  assert.ok(root.querySelectorAll('button').some(x=>x.textContent==='Verify status without collecting payment'&&!x.disabled));
})().catch(error=>{console.error(error);process.exitCode=1});
