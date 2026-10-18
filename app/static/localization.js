/* Shared IT/EN runtime: all pages, inserted dialogs, native prompts and notices. */
(()=>{'use strict';
const pairs=window.MTA_TRANSLATIONS||{},reverse={...Object.fromEntries(Object.entries(pairs).map(([en,it])=>[it,en])),...(window.MTA_TRANSLATION_ALIASES||{})};
const templates=Object.fromEntries([['it',pairs],['en',reverse]].map(([lang,map])=>[lang,Object.entries(map).filter(([p])=>p.includes('{0}')).map(([pattern,replacement])=>{const slots=[];let expr='';for(const part of pattern.split(/(\{\d+\})/)){if(/^\{\d+\}$/.test(part)){slots.push(Number(part.slice(1,-1)));expr+='(.*?)'}else expr+=part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}return {regex:new RegExp('^'+expr+'$','s'),slots,replacement}})]));
function browser(){for(const value of navigator.languages||[navigator.language||'en']){const lang=String(value).toLowerCase().split('-')[0];if(['it','en'].includes(lang))return lang}return 'en'}
function resolve(choice){return ['it','en'].includes(choice)?choice:browser()}
let choice=window.MTA_LOCALE?.choice||'auto',language=['it','en'].includes(choice)?choice:(window.MTA_LOCALE?.language||browser());
const translationCache=new Map();
function translate(value){const raw=String(value??'');if(translationCache.has(raw))return translationCache.get(raw);const result=translateUncached(raw);if(translationCache.size>=4096)translationCache.clear();translationCache.set(raw,result);return result}
function translateUncached(raw){const core=raw.trim();if(!core)return raw;const map=language==='it'?pairs:reverse;let out=map[core];
 if(out===undefined){for(const {regex,slots,replacement} of templates[language]){const match=core.match(regex);if(match){const values={};slots.forEach((n,i)=>values[n]=match[i+1]);out=replacement.replace(/\{(\d+)\}/g,(all,n)=>values[n]??all);break}}}
 if(out===undefined){for(const sep of [' · ','\n'])if(core.includes(sep)){const parts=core.split(sep),changed=parts.map(translate);if(parts.some((p,i)=>p!==changed[i])){out=changed.join(sep);break}}}
 if(out===undefined){const m=core.match(/^(.+?)(:\s*|\s+)([\d~−+].*)$/);if(m&&map[m[1]])out=map[m[1]]+m[2]+m[3]}
 if(out===undefined){const m=core.match(/^([^A-Za-zÀ-ÿ0-9]+)([A-Za-zÀ-ÿ].*)$/);if(m){const body=translate(m[2]);if(body!==m[2])out=m[1]+body}}
 if(out===undefined){const m=core.match(/^([^:\n]+):(\s+)(.*)$/s);if(m&&map[m[1]])out=map[m[1]]+':'+m[2]+m[3]}
 if(out===undefined){const changed=core.replace(/\(([^()]*)\)/g,(all,part)=>'('+translate(part)+')');if(changed!==core)out=changed}
 return out===undefined?raw:raw.slice(0,raw.length-raw.trimStart().length)+out+raw.slice(raw.trimEnd().length)}
const preserve='script,style,textarea,pre,code,[translate="no"],[data-i18n-preserve],[data-track-name],.channel-name,.track-name,.meta-value,.lyric-word';
function protectedNode(node){return node.parentElement?.closest(preserve)}
function localizeText(root){if(!protectedNode(root)){const value=translate(root.nodeValue);if(value!==root.nodeValue)root.nodeValue=value}}
function localize(root=document){if(document.documentElement.lang!==language)document.documentElement.lang=language;if(root.nodeType===3){localizeText(root);return}
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);for(const node of nodes)localizeText(node);
 for(const el of [root,...root.querySelectorAll?.('[title],[placeholder],[aria-label]')||[]]){if(el.closest?.(preserve)&&!el.matches?.('textarea'))continue;for(const attr of ['title','placeholder','aria-label'])if(el.hasAttribute?.(attr)){const value=translate(el.getAttribute(attr));if(value!==el.getAttribute(attr))el.setAttribute(attr,value)}}}
function setChoice(value){choice=['auto','it','en'].includes(value)?value:'auto';language=resolve(choice);translationCache.clear();localize();window.dispatchEvent(new CustomEvent('mta:language',{detail:{choice,language}}))}
window.addEventListener?.('languagechange',()=>{if(choice==='auto')setChoice('auto')});
window.MtaLocale={translate,localize,setChoice,resolve,get language(){return language},get choice(){return choice}};
for(const method of ['alert','confirm','prompt']){const original=window[method]?.bind(window);if(original)window[method]=(message,...args)=>original(translate(message),...args)}
if(window.Notification){const Original=window.Notification;window.Notification=class extends Original{constructor(title,options={}){super(translate(title),{...options,body:translate(options.body)})}}}
function start(){localize();const pending=new Set();let scheduled=false;new MutationObserver(changes=>{for(const change of changes){if(change.type==='childList')change.addedNodes.forEach(n=>pending.add(n));else pending.add(change.target)}if(scheduled)return;scheduled=true;queueMicrotask(()=>{scheduled=false;const batch=new Set(pending);pending.clear();for(const node of batch){if(!node.isConnected)continue;let covered=false;for(let parent=node.parentNode;parent;parent=parent.parentNode)if(batch.has(parent)){covered=true;break}if(!covered)localize(node)}})}).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['title','aria-label','placeholder']})}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
