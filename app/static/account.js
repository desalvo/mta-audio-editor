const q=s=>document.querySelector(s);
async function api(url,opt={}){opt.headers=opt.headers||{};if((opt.method||'GET').toUpperCase()!=='GET')opt.headers['X-MTA-Request']='1';const r=await fetch(url,opt);if(!r.ok)throw new Error(await r.text());return r.headers.get('content-type')?.includes('json')?r.json():r.text()}
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
let me;
async function load(){
  me=await api('/api/session');
  q('#adminLink').hidden=me.role!=='admin';
  q('#profileSummary').innerHTML=`<div class="profile-row"><b>Username</b><span>${esc(me.username)}</span></div><div class="profile-row"><b>Email</b><span>${esc(me.email)} ${me.email_confirmed?'<span class="badge ok">confermata</span>':'<span class="badge warn">da confermare</span>'}</span></div><div class="profile-row"><b>Ruolo</b><span>${esc(me.role)}</span></div>`;
  q('#profileForm').elements.display_name.value=me.display_name||'';
  q('#profileForm').elements.email.value=me.email||'';
  renderTotp();
  loadStorage();
}
async function saveProfile(e){e.preventDefault();const f=new FormData(e.target);try{const updated=await api('/api/account',{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify(Object.fromEntries(f))});if(!updated.active){alert('Email aggiornata. Controlla la nuova casella email; dopo la conferma servirà una nuova approvazione admin.');location.href='/logout';return}me=updated;load()}catch(x){alert(x.message)}}
function renderTotp(){q('#profileForm').elements.display_name.value=me.display_name||'';q('#profileForm').elements.email.value=me.email||'';q('#totpArea').innerHTML=me.totp_enabled?`<p><span class="badge ok">TOTP attivo</span></p><form id="disableTotp" class="settings-form"><label>Password<input name="password" type="password" required></label><label>Codice TOTP<input name="code" inputmode="numeric" autocomplete="one-time-code" required></label><button>Disattiva TOTP</button></form>`:`<p><span class="badge warn">TOTP non attivo</span></p><button id="beginTotp">Configura TOTP</button>`;if(q('#beginTotp'))q('#beginTotp').onclick=beginTotp;if(q('#disableTotp'))q('#disableTotp').onsubmit=disableTotp}
async function beginTotp(){const d=await api('/api/account/totp/begin',{method:'POST'});q('#totpArea').innerHTML=`<p>Scansiona il QR code con il cellulare e inserisci il codice generato.</p><img class="totp-qr" src="/api/account/totp/qr?nonce=${Date.now()}" alt="QR TOTP"><p>Chiave manuale: <code>${esc(d.secret)}</code></p><form id="enableTotp" class="settings-form"><label>Codice a 6 cifre<input name="code" inputmode="numeric" autocomplete="one-time-code" required></label><button>Attiva TOTP</button></form>`;q('#enableTotp').onsubmit=enableTotp}
async function enableTotp(e){e.preventDefault();try{await api('/api/account/totp/enable',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({code:new FormData(e.target).get('code')})});me=await api('/api/session');renderTotp()}catch(x){alert(x.message)}}
async function disableTotp(e){e.preventDefault();const f=new FormData(e.target);try{await api('/api/account/totp/disable',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({password:f.get('password'),code:f.get('code')})});me=await api('/api/session');renderTotp()}catch(x){alert(x.message)}}
q('#profileForm').onsubmit=saveProfile;
q('#passwordForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('/api/account/password',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(Object.fromEntries(f))});alert('Password aggiornata. Accedi nuovamente.');location.href='/login'}catch(x){alert(x.message)}}
load();

function fmtBytes(n){n=Number(n||0);if(n<1024)return n+' B';const u=['KB','MB','GB','TB'];let i=-1;do{n/=1024;i++}while(n>=1024&&i<u.length-1);return n.toFixed(n>=10?1:2)+' '+u[i]}
async function loadStorage(){try{const d=await api('/api/storage'),w=(d.workspaces||[])[0];q('#storageSummary').innerHTML=w?`<div class="profile-row"><b>Usato</b><span>${fmtBytes(w.used_bytes)}</span></div><div class="profile-row"><b>Quota</b><span>${w.quota_bytes?fmtBytes(w.quota_bytes):'Illimitata'}</span></div><div class="profile-row"><b>Disponibile</b><span>${w.remaining_bytes==null?'—':fmtBytes(w.remaining_bytes)}</span></div>`:'Nessun workspace disponibile.'}catch(e){q('#storageSummary').textContent='Impossibile leggere lo spazio workspace.'}}
