(() => {
  'use strict';
  if (document.body.classList.contains('native-single-user')) return;
  const language = () => (document.documentElement.lang || '').startsWith('it');
  const tr = (it, en) => language() ? it : en;
  const make = (tag, text = '') => {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  };
  const button = (label, action) => {
    const node = make('button', label);
    node.type = 'button';
    node.addEventListener('click', action);
    return node;
  };
  async function api(path, options = {}) {
    const response = await fetch('/api/messages' + path, {
      ...options, cache: 'no-store', headers: {'X-MTA-Request': '1', ...options.headers}
    });
    if (!response.ok) {
      const detail = (await response.json().catch(() => ({}))).detail;
      const error = new Error(typeof detail === 'string' ? detail : tr('Richiesta non riuscita', 'Request failed'));
      error.status = response.status;
      throw error;
    }
    return response.json();
  }
  const post = (path, payload) => api(path, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const label = peer => peer.display_name && peer.display_name !== peer.username
    ? peer.display_name + ' (@' + peer.username + ')' : '@' + peer.username;

  const anchor = make('span');
  anchor.className = 'mta-message-anchor';
  anchor.hidden = true;
  const bell = button('🔔', toggle);
  bell.className = 'mta-message-bell';
  bell.setAttribute('aria-controls', 'mta-message-panel');
  bell.setAttribute('aria-expanded', 'false');
  const badge = make('span', '0');
  badge.className = 'mta-message-badge';
  badge.setAttribute('aria-hidden', 'true');
  bell.append(badge);
  anchor.append(bell);
  const toolbar = document.querySelector('.header-actions, .settings-top nav, header nav, header');
  if (!toolbar) anchor.classList.add('mta-message-fixed');
  (toolbar || document.body).append(anchor);

  const panel = make('dialog');
  panel.id = 'mta-message-panel';
  panel.className = 'mta-message-panel';
  panel.setAttribute('aria-labelledby', 'mta-message-heading');
  const top = make('div');
  top.className = 'mta-message-top';
  const heading = make('h2', tr('Messaggi', 'Messages'));
  heading.id = 'mta-message-heading';
  const close = button('×', () => panel.close());
  close.setAttribute('aria-label', tr('Chiudi messaggi', 'Close messages'));
  top.append(heading, close);
  const content = make('div');
  content.className = 'mta-message-content';
  const sidebar = make('aside');
  const search = make('input');
  search.type = 'search';
  search.maxLength = 64;
  search.placeholder = tr('Cerca utenti (min. 2 caratteri)', 'Find users (min. 2 characters)');
  search.setAttribute('aria-label', search.placeholder);
  const results = make('div');
  const list = make('div');
  list.className = 'mta-message-threads';
  list.setAttribute('aria-label', tr('Conversazioni', 'Conversations'));
  const moreThreads = button(tr('Altre conversazioni', 'More conversations'), () => {
    loadThreads(nextThreads).catch(failure);
  });
  moreThreads.hidden = true;
  sidebar.append(search, results, list, moreThreads);

  const conversation = make('section');
  conversation.className = 'mta-message-conversation';
  const peerName = make('h3', tr('Seleziona o cerca un utente', 'Select or find a user'));
  const log = make('div');
  log.className = 'mta-message-log';
  log.setAttribute('role', 'region');
  log.setAttribute('aria-label', tr('Cronologia messaggi', 'Message history'));
  log.tabIndex = 0;
  const older = button(tr('Messaggi precedenti', 'Older messages'), () => loadHistory(true).catch(failure));
  older.hidden = true;
  log.append(older);
  const form = make('form');
  form.hidden = true;
  const input = make('textarea');
  input.maxLength = 4000;
  input.rows = 2;
  input.placeholder = tr('Scrivi un messaggio', 'Write a message');
  input.setAttribute('aria-label', input.placeholder);
  const file = make('input');
  file.type = 'file';
  file.accept = 'image/png,image/jpeg,image/gif,image/webp,audio/*,video/mp4,video/webm';
  file.setAttribute('aria-label', tr('Allega immagine, audio o video', 'Attach an image, audio or video'));
  const sendFile = button(tr('Invia allegato', 'Send attachment'), sendAttachment);
  const send = make('button', tr('Invia', 'Send'));
  send.type = 'submit';
  form.append(input, send, file, sendFile);
  const status = make('p');
  status.className = 'mta-message-status';
  status.setAttribute('role', 'status');
  conversation.append(peerName, log, form, status);
  content.append(sidebar, conversation);
  panel.append(top, content);
  document.body.append(panel);

  let active = null, historyVersion = 0, searchVersion = 0, searchTimer;
  let nextHistory = null, nextThreads = null, threadItems = [], busy = false, polling = false;
  let newestRead = 0;
  const rendered = new Set();
  function failure(error) {
    if (error.status === 401 || error.status === 403) {
      anchor.hidden = true;
      if (panel.open) panel.close();
      active = null;
      historyVersion++;
      searchVersion++;
      threadItems = [];
      nextThreads = null;
      nextHistory = null;
      form.hidden = older.hidden = moreThreads.hidden = true;
      input.value = file.value = search.value = '';
      list.replaceChildren();
      results.replaceChildren();
      peerName.textContent = tr('Seleziona o cerca un utente', 'Select or find a user');
      rendered.clear();
      log.replaceChildren(older);
    }
    status.textContent = error.message;
  }
  function showCount(count) {
    badge.textContent = count > 99 ? '99+' : String(count);
    const title = tr('Messaggi non letti', 'Unread messages') + ' · ' + count;
    bell.setAttribute('aria-label', title);
    bell.title = title;
    anchor.hidden = false;
  }
  async function refreshUnread() {
    showCount((await api('/unread')).unread);
  }
  function toggle() {
    if (panel.open) panel.close();
    else {
      panel.show();
      bell.setAttribute('aria-expanded', 'true');
      search.focus();
      poll();
    }
  }
  panel.addEventListener('close', () => {
    bell.setAttribute('aria-expanded', 'false');
    bell.focus();
  });
  panel.addEventListener('keydown', event => {
    event.stopPropagation();
    if (event.key === 'Escape') panel.close();
  });
  top.addEventListener('pointerdown', event => {
    if (event.target.closest('button') || event.button !== 0) return;
    const bounds = panel.getBoundingClientRect();
    const x = event.clientX - bounds.left, y = event.clientY - bounds.top;
    top.setPointerCapture(event.pointerId);
    const move = ev => {
      if (ev.pointerId !== event.pointerId) return;
      panel.style.right = 'auto';
      panel.style.left = Math.max(0, Math.min(innerWidth - bounds.width, ev.clientX - x)) + 'px';
      panel.style.top = Math.max(0, Math.min(innerHeight - bounds.height, ev.clientY - y)) + 'px';
    };
    top.addEventListener('pointermove', move);
    top.addEventListener('lostpointercapture', () => top.removeEventListener('pointermove', move), {once: true});
  });
  window.addEventListener('resize', () => {
    panel.style.left = panel.style.top = panel.style.right = '';
  });
  async function loadThreads(before) {
    const result = await api('/threads' + (before ? '?before=' + before : ''));
    if (before) {
      const known = new Set(threadItems.map(item => item.id));
      threadItems.push(...result.items.filter(item => !known.has(item.id)));
    } else {
      const newest = new Set(result.items.map(item => item.id));
      threadItems = [...result.items, ...threadItems.slice(50).filter(item => !newest.has(item.id))];
    }
    if (before || threadItems.length <= 50) nextThreads = result.next_before;
    list.replaceChildren(...threadItems.map(item => {
      const node = button(label(item) + (item.unread ? ' · ' + item.unread : ''), () => openPeer(item));
      node.setAttribute('aria-pressed', String(item.id === active?.id));
      return node;
    }));
    moreThreads.hidden = !nextThreads;
  }
  search.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const query = search.value.trim(), version = ++searchVersion;
    results.replaceChildren();
    if (query.length < 2) return;
    searchTimer = setTimeout(async () => {
      try {
        const users = await api('/contacts?q=' + encodeURIComponent(query));
        if (version !== searchVersion) return;
        results.replaceChildren(...(users.length
          ? users.map(user => button(label(user), () => openPeer(user)))
          : [make('p', tr('Nessun utente trovato', 'No users found'))]));
      } catch (error) {
        if (version === searchVersion) failure(error);
      }
    }, 250);
  });
  function openPeer(peer) {
    if (busy || active?.id === peer.id) return;
    active = peer;
    historyVersion++;
    peerName.textContent = label(peer);
    nextHistory = null;
    newestRead = 0;
    rendered.clear();
    log.replaceChildren(older);
    older.hidden = true;
    form.hidden = true;
    input.value = '';
    file.value = '';
    search.value = '';
    searchVersion++;
    results.replaceChildren();
    status.textContent = '';
    loadHistory().catch(failure);
    loadThreads().catch(failure);
  }
  function messageNode(message, viewer) {
    const article = make('article');
    article.className = message.sender === viewer ? 'mta-message-own' : 'mta-message-received';
    const date = new Date(message.created_at * 1000);
    const time = make('time', date.toLocaleString());
    time.dateTime = date.toISOString();
    article.append(time);
    if (message.text) article.append(make('p', message.text));
    if (message.mime) {
      const kind = message.mime.split('/')[0];
      if (['image', 'audio', 'video'].includes(kind)) {
        const url = '/api/messages/attachments/' + message.id;
        const media = make(kind === 'image' ? 'img' : kind);
        if (kind === 'image') {
          media.alt = tr('Immagine allegata', 'Attached image');
          media.loading = 'lazy';
        } else {
          media.controls = true;
          media.preload = 'none';
          if (kind === 'video') media.playsInline = true;
        }
        media.src = url;
        const download = make('a', tr('Scarica allegato', 'Download attachment'));
        download.href = url;
        download.download = '';
        article.append(media, download);
      }
    }
    return article;
  }
  async function loadHistory(previous = false) {
    if (!active || (previous && !nextHistory)) return;
    const peer = active.id, version = historyVersion, before = previous ? nextHistory : null;
    if (previous) older.disabled = true;
    try {
      const data = await api('/threads/' + peer + (before ? '?before=' + before : ''));
      if (version !== historyVersion || !panel.open) return;
      const position = log.scrollTop, height = log.scrollHeight;
      const nearEnd = height - position - log.clientHeight < 70;
      const fragment = document.createDocumentFragment();
      const wasEmpty = !rendered.size;
      for (const message of data.items) {
        if (rendered.has(message.id)) continue;
        rendered.add(message.id);
        fragment.append(messageNode(message, data.viewer));
      }
      if (previous) {
        older.after(fragment);
        log.scrollTop = position + log.scrollHeight - height;
      } else {
        log.append(fragment);
        if (nearEnd || wasEmpty) log.scrollTop = log.scrollHeight;
      }
      if (previous || wasEmpty) nextHistory = data.next_before;
      older.hidden = !nextHistory;
      form.hidden = !data.can_send;
      if (!previous && !document.hidden && document.hasFocus()) {
        const last = data.items.at(-1)?.id || 0;
        if (last > newestRead) {
          await post('/threads/' + peer + '/read', {through: last});
          if (version === historyVersion) newestRead = last;
          await refreshUnread();
        }
      }
    } finally {
      if (previous) older.disabled = false;
    }
  }
  async function transmit(action, clear) {
    if (!active || busy) return;
    busy = true;
    send.disabled = sendFile.disabled = true;
    status.textContent = tr('Invio in corso…', 'Sending…');
    try {
      await action(active.id);
      clear();
      status.textContent = '';
      await loadHistory();
      log.scrollTop = log.scrollHeight;
      await loadThreads();
    } catch (error) {
      failure(error);
    } finally {
      busy = false;
      send.disabled = sendFile.disabled = false;
    }
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const text = input.value.trim();
    if (text) transmit(peer => post('/threads/' + peer, {text}), () => {
      if (input.value.trim() === text) input.value = '';
    });
  });
  function sendAttachment() {
    const selected = file.files[0];
    if (!selected) {
      file.focus();
      return;
    }
    if (selected.size > 20 * 1024 * 1024) {
      status.textContent = tr('Limite allegato: 20 MiB', 'Attachment limit: 20 MiB');
      return;
    }
    transmit(peer => api('/threads/' + peer + '/attachment', {method: 'POST', body: selected}), () => {
      if (file.files[0] === selected) file.value = '';
    });
  }
  async function poll() {
    if (document.hidden || polling) return;
    polling = true;
    try {
      await refreshUnread();
      if (panel.open) {
        await loadHistory();
        await loadThreads();
      }
    } catch (error) {
      failure(error);
    } finally {
      polling = false;
    }
  }
  if (new URLSearchParams(location.search).get('messages') === '1') {
    refreshUnread().then(toggle).catch(failure);
  } else {
    poll();
  }
  setInterval(poll, 6000);
  document.addEventListener('visibilitychange', poll);
  window.addEventListener('focus', poll);
})();
