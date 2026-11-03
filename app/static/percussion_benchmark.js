/* MTA Percussion Benchmark & Validation: no client-side quality approval. */
(() => {
  'use strict';
  const BASE = '/api/admin/ai-benchmarks';
  const SCORE_KEYS = ['isolation', 'contamination', 'naturalness', 'transients', 'completeness', 'overall'];
  const SCORE_LABELS = {
    isolation: ['Isolation', 'Isolamento'], contamination: ['Contamination (5 = negligible)', 'Contaminazione (5 = trascurabile)'],
    naturalness: ['Naturalness', 'Naturalezza'], transients: ['Transient preservation', 'Conservazione transienti'],
    completeness: ['Completeness', 'Completezza'], overall: ['Overall quality', 'Qualità complessiva']
  };
  const STATUS_LABELS = {
    ready: ['Ready', 'Pronto'], available: ['Available', 'Disponibile'], installed: ['Installed', 'Installato'],
    not_installed: ['Not installed', 'Non installato'], not_authorized: ['Not authorized', 'Non autorizzato'],
    unauthorized: ['Not authorized', 'Non autorizzato'], incompatible: ['Incompatible', 'Incompatibile'],
    unsupported: ['Adapter unavailable', 'Adapter non disponibile'], blocked: ['Blocked', 'Bloccato'],
    configured_unverified: ['Configured; installation not verified', 'Configurato; installazione non verificata'],
    queued: ['Queued', 'In coda'], pending: ['Pending', 'In attesa'], running: ['Running', 'In esecuzione'],
    completed: ['Inference completed', 'Inferenza completata'], failed: ['Inference failed', 'Inferenza fallita'],
    invalid: ['Invalid result', 'Risultato non valido'], cancelled: ['Cancelled', 'Annullato'],
    validated_automatically: ['Automatically validated', 'Validato automaticamente'],
    inference_failed: ['Inference failed', 'Inferenza fallita'], invalid_result: ['Invalid result', 'Risultato non valido'],
    dataset_unavailable: ['Dataset unavailable', 'Dataset non disponibile'], disabled: ['Disabled', 'Disattivato'],
    awaiting_human_validation: ['Awaiting human validation', 'In attesa di validazione umana'],
    approved: ['Manually approved', 'Approvato manualmente'], manually_approved: ['Manually approved', 'Approvato manualmente'],
    approved_manually: ['Manually approved', 'Approvato manualmente']
  };
  const tr = (en, it) => (window.MtaLocale?.language || document.documentElement?.lang || 'en').startsWith('it') ? it : en;
  const label = pair => tr(...pair);
  const statusLabel = value => STATUS_LABELS[value] ? label(STATUS_LABELS[value]) : String(value || '—');
  const formatNumber = value => Number.isFinite(value) ? Number(value.toFixed(3)).toString() : '—';

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }
  function button(text, action, className) {
    const node = element('button', text, className || 'utility-btn');
    node.type = 'button'; node.addEventListener('click', action); return node;
  }
  function field(title, input) {
    const wrapper = element('label', null, 'benchmark-field');
    wrapper.append(element('span', title), input); return wrapper;
  }
  function select(options, value) {
    const input = element('select');
    for (const [key, title] of options) { const option = element('option', title); option.value = key; input.append(option); }
    if (value !== undefined) input.value = value;
    return input;
  }
  function errorText(error) { return error?.message || String(error); }
  function safeAudioUrl(value) {
    if (!value) return null;
    try {
      const url = new URL(value, location.href);
      return url.origin === location.origin && url.pathname.startsWith(BASE + '/') ? url.href : null;
    } catch { return null; }
  }
  function candidateLabel(result) {
    if (result.identity_revealed === true || result.rated === true) {
      const name = result.identity?.name || result.model_name || result.model_id || result.label || tr('Rated candidate', 'Candidato valutato');
      const version = result.identity?.version || result.model_version;
      return name + (version ? ' · ' + version : '');
    }
    return result.label || result.candidate_label || tr('Blind candidate', 'Candidato cieco');
  }
  function validateRating(values) {
    const scores = {};
    for (const key of SCORE_KEYS) {
      const value = Number(values.scores?.[key]);
      if (!Number.isInteger(value) || value < 1 || value > 5) throw Error(tr('Rate all six criteria from 1 to 5.', 'Valuta tutti i sei criteri da 1 a 5.'));
      scores[key] = value;
    }
    if (!['professional', 'limited', 'rejected'].includes(values.decision)) throw Error(tr('Choose a final assessment.', 'Scegli una valutazione finale.'));
    if (values.explicit_approval !== undefined && typeof values.explicit_approval !== 'boolean') throw Error(tr('Invalid listening confirmation.', 'Conferma di ascolto non valida.'));
    const explicitApproval = values.explicit_approval === true;
    if (values.decision === 'professional' && !explicitApproval) throw Error(tr('Explicitly confirm your listening assessment for this excerpt.', 'Conferma esplicitamente la valutazione di ascolto di questo estratto.'));
    if (values.decision !== 'professional' && explicitApproval) throw Error(tr('Professional listening confirmation requires the professional decision.', 'La conferma professionale richiede la relativa valutazione professionale.'));
    const comment = String(values.comment || '').trim();
    if (comment.length > 4000) throw Error(tr('The comment is too long (maximum 4000 characters).', 'Il commento è troppo lungo (massimo 4000 caratteri).'));
    return {scores, decision: values.decision, comment, explicit_approval: explicitApproval};
  }
  function excerptBounds(item, duration) {
    const start = Math.max(0, Number(item?.start) || 0);
    const available = Number.isFinite(duration) && duration > 0 ? duration : Infinity;
    const requestedEnd = Number(item?.end);
    const end = Math.min(available, Number.isFinite(requestedEnd) && requestedEnd > start ? requestedEnd : start + 20);
    return {start: Math.min(start, Math.max(0, end - 0.01)), end};
  }
  function switchPosition(previous, bounds, full) {
    const previousTime = Number.isFinite(previous) ? previous : bounds.start;
    return full ? Math.max(0, previousTime) : Math.max(bounds.start, Math.min(previousTime, bounds.end - 0.01));
  }
  function categoryRows(categories) {
    if (Array.isArray(categories)) return categories;
    if (!categories || typeof categories !== 'object') return [];
    return Object.entries(categories).filter(([, value]) => value && typeof value === 'object').map(([category, value]) => ({
      ...value, category: value.category || category, label: value.label || tr('Category summary', 'Riepilogo categoria'),
      metrics: value.metrics || {...value, si_sdr_db: value.mean_si_sdr_db ?? value.si_sdr_db}
    }));
  }
  async function request(path, body, options = {}) {
    const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
    const response = await fetch(BASE + path, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {'X-MTA-Request': '1', ...(isForm ? {} : {'Content-Type': 'application/json'})},
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body), ...options
    });
    let data;
    try { data = await response.json(); } catch { throw Error(tr('Invalid server response.', 'Risposta del server non valida.') + ' HTTP ' + response.status); }
    if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : tr('Request failed.', 'Richiesta fallita.') + ' HTTP ' + response.status);
    return data;
  }
  function drawWaveform(canvas, peaks) {
    const context = canvas.getContext?.('2d');
    if (!context) return;
    const width = canvas.width, height = canvas.height;
    context.clearRect(0, 0, width, height); context.strokeStyle = '#66c4ff'; context.lineWidth = 1;
    context.beginPath(); context.moveTo(0, height / 2); context.lineTo(width, height / 2); context.stroke();
    if (!Array.isArray(peaks) || !peaks.length) return;
    context.beginPath();
    for (let x = 0; x < width; x++) {
      const sample = peaks[Math.min(peaks.length - 1, Math.floor(x * peaks.length / width))];
      const minimum = Array.isArray(sample) ? Number(sample[0]) : -Math.abs(Number(sample));
      const maximum = Array.isArray(sample) ? Number(sample[1]) : Math.abs(Number(sample));
      if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) continue;
      context.moveTo(x, height / 2 - Math.max(-1, Math.min(1, maximum)) * height * .46);
      context.lineTo(x, height / 2 - Math.max(-1, Math.min(1, minimum)) * height * .46);
    }
    context.stroke();
  }

  function createView(host) {
    let disposed = false, timer = null, campaignId = null, campaignData = null, caseId = null, generation = 0, savedCampaigns = [];
    let blindData = null, selectedAudio = null, levelMatched = false, fullLength = false, playbackGeneration = 0;
    const controller = new AbortController();
    const call = (path, body, options = {}) => request(path, body, {signal: controller.signal, ...options});
    const alive = () => !disposed && host.isConnected;
    const top = element('div', null, 'benchmark-top');
    const status = element('p', '', 'benchmark-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const setup = element('section', null, 'benchmark-setup');
    const campaigns = element('section', null, 'benchmark-campaigns');
    const campaignPanel = element('section', null, 'benchmark-current');
    const listeningPanel = element('section', null, 'benchmark-listening');
    const audio = element('audio'); audio.controls = true; audio.preload = 'metadata'; audio.className = 'benchmark-audio';
    const waveform = element('canvas'); waveform.width = 800; waveform.height = 100;
    waveform.className = 'benchmark-waveform'; waveform.setAttribute('aria-label', tr('Audio waveform', 'Waveform audio')); waveform.setAttribute('role', 'img');
    const nowPlaying = element('p', '', 'benchmark-now-playing');
    const playback = element('div', null, 'benchmark-playback');
    const loopCheck = element('input'); loopCheck.type = 'checkbox'; loopCheck.checked = true;
    const fullCheck = element('input'); fullCheck.type = 'checkbox';
    const matchCheck = element('input'); matchCheck.type = 'checkbox';
    const volume = element('input'); volume.type = 'range'; volume.min = '0'; volume.max = '1'; volume.step = '.01'; volume.value = '.8'; audio.volume = .8;
    let bounds = {start: 0, end: 20};
    const fail = error => { if (error?.name !== 'AbortError' && alive()) status.textContent = errorText(error); };
    const task = action => async event => { try { await action(event); } catch (error) { fail(error); } };

    host.replaceChildren(); host.classList.add('mta-benchmark');
    top.append(element('h2', tr('AI benchmark and validation', 'Benchmark e validazione AI')),
      element('p', tr('Automatic measurements and human listening are separate. No model is professionally approved by completing this screen.',
        'Misure automatiche e ascolto umano sono separati. Il completamento di questa schermata non approva professionalmente un modello.')));
    host.append(top, status, setup, campaigns, campaignPanel, listeningPanel);
    const matchLabel = field(tr('Level-matched listening copy', 'Copia di ascolto con livello comparabile'), matchCheck);
    const loopLabel = field(tr('Loop this excerpt', 'Ripeti questo estratto'), loopCheck);
    const fullLabel = field(tr('Full-length audio', 'Audio integrale'), fullCheck);
    playback.append(nowPlaying, audio, waveform, loopLabel, fullLabel, matchLabel, field(tr('Volume', 'Volume'), volume));
    volume.addEventListener('input', () => { audio.volume = Math.max(0, Math.min(1, Number(volume.value) || 0)); });
    fullCheck.addEventListener('change', () => { fullLength = fullCheck.checked; audio.currentTime = Math.min(Number.isFinite(audio.duration) ? Math.max(0, audio.duration - .01) : Infinity, switchPosition(audio.currentTime, bounds, fullLength)); });
    matchCheck.addEventListener('change', task(async () => { levelMatched = matchCheck.checked; if (selectedAudio) await play(selectedAudio, !audio.paused); }));
    audio.addEventListener('timeupdate', () => {
      if (!fullLength && loopCheck.checked && audio.currentTime >= bounds.end) { audio.currentTime = bounds.start; if (audio.paused) audio.play().catch(fail); }
      else if (!fullLength && !loopCheck.checked && audio.currentTime >= bounds.end) audio.pause();
    });
    audio.addEventListener('ended', () => { if (loopCheck.checked) { audio.currentTime = fullLength ? 0 : bounds.start; audio.play().catch(fail); } });
    audio.addEventListener('error', () => { if (alive()) status.textContent = tr('Audio unavailable or expired. Refresh the campaign.', 'Audio non disponibile o scaduto. Aggiorna la campagna.'); });

    async function play(item, resume = true) {
      const playbackToken = ++playbackGeneration;
      const value = levelMatched && item.matched_audio_url ? item.matched_audio_url : item.audio_url;
      const url = safeAudioUrl(value);
      if (!url) throw Error(tr('Audio is not available from this server.', 'Audio non disponibile da questo server.'));
      const oldTime = audio.currentTime;
      selectedAudio = item;
      matchCheck.disabled = !item.matched_audio_url;
      nowPlaying.textContent = item.label + (levelMatched && item.matched_audio_url ? ' · ' + tr('level matched', 'livello comparabile') : ' · ' + tr('original file', 'file originale'));
      drawWaveform(waveform, item.peaks);
      if (audio.src !== url) {
        audio.pause(); audio.src = url;
        await new Promise((resolve, reject) => {
          const clean = () => { audio.removeEventListener('loadedmetadata', loaded); audio.removeEventListener('error', failed); };
          const loaded = () => { clean(); resolve(); };
          const failed = () => { clean(); reject(Error(tr('Cannot load this audio.', 'Impossibile caricare questo audio.'))); };
          audio.addEventListener('loadedmetadata', loaded, {once: true}); audio.addEventListener('error', failed, {once: true}); audio.load();
        });
      }
      if (!alive() || playbackToken !== playbackGeneration) return;
      bounds = excerptBounds(blindData?.case?.excerpt, audio.duration);
      audio.currentTime = Math.min(Number.isFinite(audio.duration) ? Math.max(0, audio.duration - .01) : Infinity, switchPosition(oldTime, bounds, fullLength));
      if (resume) await audio.play();
    }

    function renderCatalog(data) {
      setup.replaceChildren();
      const details = element('details'); details.open = true;
      details.append(element('summary', tr('New reproducible campaign', 'Nuova campagna riproducibile')));
      const title = element('input'); title.type = 'text'; title.maxLength = 200; title.value = tr('Percussion comparison', 'Confronto percussioni');
      const kind = select([['experimental', tr('Experimental campaign', 'Campagna sperimentale')], ['release', tr('Release validation', 'Validazione di rilascio')]], 'experimental');
      const seed = element('input'); seed.type = 'number'; seed.min = '0'; seed.max = '2147483647'; seed.value = '42';
      const kick = element('input'); kick.type = 'checkbox'; kick.checked = true;
      const categoryOptions = [['percussion', tr('Include as percussion', 'Includi fra le percussioni')], ['excluded', tr('Exclude', 'Escludi')]];
      const clap = select(categoryOptions, 'excluded'), timpani = select(categoryOptions, 'excluded');
      const sourceMode = select([['both', tr('DRUMS and original mix', 'DRUMS e mix originale')], ['drums', 'DRUMS'], ['mix', tr('Original mix', 'Mix originale')]], 'both');
      const config = element('div', null, 'benchmark-grid');
      config.append(field(tr('Campaign name', 'Nome campagna'), title), field(tr('Purpose', 'Tipo'), kind), field(tr('Reproducible seed', 'Seme riproducibile'), seed),
        field(tr('Include kick (default)', 'Includi kick (predefinito)'), kick), field('Clap', clap), field('Timpani', timpani), field(tr('Input comparison','Confronto sorgenti'), sourceMode));
      details.append(config);
      const modelChecks = [], datasetChecks = [];
      details.append(element('h3', tr('Models and availability', 'Modelli e disponibilità')));
      for (const model of data.models || []) {
        const card = element('article', null, 'benchmark-model');
        const check = element('input'); check.type = 'checkbox'; check.value = model.id;
        check.disabled = model.enabled === false || ['not_authorized', 'unauthorized', 'incompatible', 'unsupported', 'blocked'].includes(model.status);
        modelChecks.push(check); card.append(field(model.name || model.id, check));
        const detail = [statusLabel(model.status), model.version, typeof model.license === 'string' ? model.license : model.license?.status].filter(Boolean).join(' · ');
        card.append(element('p', detail), element('small', model.reason || model.status_reason || ''));
        if (model.checkpoint_sha256) card.append(element('code', 'SHA-256 ' + model.checkpoint_sha256));
        if (model.status === 'configured_unverified') card.append(button(tr('Verify installation', 'Verifica installazione'), task(async event => {
          event.currentTarget.disabled = true;
          try { await call('/models/' + encodeURIComponent(model.id) + '/verify', {}); await loadCatalog(); }
          finally { event.currentTarget.disabled = false; }
        })));
        if (typeof model.enabled === 'boolean') {
          const enabled = element('input'); enabled.type = 'checkbox'; enabled.checked = model.enabled;
          enabled.addEventListener('change', task(async () => {
            enabled.disabled = true;
            try { await call('/models/' + encodeURIComponent(model.id) + '/enabled', {enabled: enabled.checked}, {method: 'PUT'}); await loadCatalog(); }
            catch (error) { enabled.checked = model.enabled; throw error; }
            finally { enabled.disabled = false; }
          }));
          card.append(field(tr('Enabled for benchmark selection', 'Attivo per la selezione benchmark'), enabled));
        }
        details.append(card);
      }
      details.append(element('h3', tr('Datasets', 'Dataset')));
      for (const dataset of data.datasets || []) {
        const check = element('input'); check.type = 'checkbox'; check.value = dataset.id; check.disabled = !dataset.prepared; check.checked = !!dataset.prepared;
        datasetChecks.push(check);
        const count = Array.isArray(dataset.cases) ? dataset.cases.length : Number(dataset.cases || 0);
        details.append(field((dataset.name || dataset.id) + ' · ' + count + ' ' + tr('cases', 'casi') + ' · ' + (dataset.prepared ? tr('prepared', 'preparato') : tr('not prepared', 'non preparato')), check));
      }
      const rights = element('input'); rights.type = 'checkbox';
      details.append(field(tr('I have the rights to use every uploaded recording for this benchmark. This declaration does not approve model quality.', 'Ho i diritti per utilizzare tutte le registrazioni caricate nel benchmark. La dichiarazione non approva la qualità del modello.'), rights));
      const importFile = element('input'); importFile.type = 'file'; importFile.accept = '.zip,application/zip'; importFile.hidden = true;
      importFile.addEventListener('change', task(async () => {
        const file = importFile.files?.[0]; if (!file) return;
        if (!rights.checked) throw Error(tr('Confirm recording rights before import.', 'Conferma i diritti delle registrazioni prima di importare.'));
        const body = new FormData(); body.append('file', file); body.append('acknowledge_rights', 'true');
        await call('/datasets/import', body); importFile.value = ''; rights.checked = false; await loadCatalog();
        status.textContent = tr('Dataset imported with provenance. Human quality approval remains separate.', 'Dataset importato con provenienza. L’approvazione umana della qualità rimane distinta.');
      }));
      details.append(button(tr('Import recording dataset ZIP', 'Importa dataset di registrazioni ZIP'), task(async () => {
        if (!rights.checked) throw Error(tr('Confirm recording rights before import.', 'Conferma i diritti delle registrazioni prima di importare.'));
        importFile.click();
      })), importFile);
      const actions = element('div', null, 'benchmark-actions');
      actions.append(button(tr('Prepare original synthetic corpus', 'Prepara corpus sintetico originale'), task(async event => {
        event.currentTarget.disabled = true; status.textContent = tr('Preparing corpus…', 'Preparazione corpus…');
        try { await call('/datasets/synthetic', {}); await loadCatalog(); status.textContent = tr('Corpus prepared. Real recordings remain a separate requirement.', 'Corpus preparato. Le registrazioni reali restano un requisito distinto.'); }
        finally { event.currentTarget.disabled = false; }
      })), button(tr('Create campaign', 'Crea campagna'), task(async event => {
        const modelIds = modelChecks.filter(c => c.checked && !c.disabled).map(c => c.value);
        const datasetIds = datasetChecks.filter(c => c.checked && !c.disabled).map(c => c.value);
        const seedValue = Number(seed.value);
        if (!title.value.trim() || !modelIds.length || !datasetIds.length) throw Error(tr('Enter a name and select models and prepared datasets.', 'Inserisci un nome e seleziona modelli e dataset preparati.'));
        if (!Number.isInteger(seedValue) || seedValue < 0 || seedValue > 2147483647) throw Error(tr('Invalid seed.', 'Seme non valido.'));
        event.currentTarget.disabled = true;
        try {
          const created = await call('/campaigns', {title: title.value.trim(), kind: kind.value, model_ids: modelIds, dataset_ids: datasetIds,
            seed: seedValue, options: {include_kick: kick.checked, clap: clap.value, timpani: timpani.value, source_mode: sourceMode.value}});
          const item = created.campaign || created; await loadCampaigns(); await openCampaign(item.id);
        } finally { event.currentTarget.disabled = false; }
      }), 'utility-btn primary'));
      details.append(actions); setup.append(details);
    }

    async function loadCatalog() { const data = await call('/catalog'); if (alive()) renderCatalog(data); }
    async function loadCampaigns() {
      const data = await call('/campaigns'); if (!alive()) return;
      savedCampaigns = data.campaigns || [];
      campaigns.replaceChildren(); campaigns.append(element('h3', tr('Saved campaigns', 'Campagne salvate')));
      const row = element('div', null, 'benchmark-actions');
      const choices = select([['', tr('Select a campaign…', 'Seleziona una campagna…')], ...(data.campaigns || []).map(c => [c.id, `${c.title} · ${c.kind === 'release' ? tr('release', 'rilascio') : tr('experimental', 'sperimentale')} · ${statusLabel(c.status)}`])], campaignId || '');
      choices.setAttribute('aria-label', tr('Saved campaign', 'Campagna salvata'));
      choices.addEventListener('change', task(async () => { if (choices.value) await openCampaign(choices.value); })); row.append(choices);
      row.append(button(tr('Refresh', 'Aggiorna'), task(async () => { await loadCampaigns(); if (campaignId) await openCampaign(campaignId); })));
      const restore = element('input'); restore.type = 'file'; restore.accept = '.zip,application/zip'; restore.hidden = true;
      restore.addEventListener('change', task(async () => {
        const file = restore.files?.[0]; if (!file) return;
        const body = new FormData(); body.append('file', file);
        status.textContent = tr('Restoring campaign…', 'Ripristino campagna…');
        const restored = await call('/campaigns/restore', body); await loadCampaigns();
        const item = restored.campaign || restored; if (item.id) await openCampaign(item.id);
        restore.value = ''; status.textContent = tr('Campaign restored without overwriting an existing campaign.', 'Campagna ripristinata senza sovrascrivere una campagna esistente.');
      }));
      row.append(button(tr('Restore campaign ZIP', 'Ripristina campagna ZIP'), () => restore.click()), restore); campaigns.append(row);
      if (!(data.campaigns || []).length) campaigns.append(element('p', tr('No saved campaigns.', 'Nessuna campagna salvata.')));
    }

    function renderMetrics(rows, title) {
      const section = element('section', null, 'benchmark-metrics'); section.append(element('h4', title));
      if (!rows.length) { section.append(element('p', tr('No measurements available.', 'Nessuna misura disponibile.'))); return section; }
      const table = element('table'); table.className = 'benchmark-table';
      const head = element('tr');
      for (const text of [tr('Candidate / category', 'Candidato / categoria'), 'SI-SDR (dB)', tr('Improvement (dB)', 'Miglioramento (dB)'), tr('Input/output alignment', 'Allineamento input/output'), tr('Status', 'Stato')]) head.append(element('th', text));
      const thead = element('thead'); thead.append(head); table.append(thead);
      const body = element('tbody');
      const values = rows.map(r => r.metrics?.si_sdr_db ?? r.metrics?.si_sdr ?? r.si_sdr_db).filter(Number.isFinite);
      const minimum = Math.min(0, ...values), maximum = Math.max(1, ...values);
      for (const item of rows) {
        const metrics = item.metrics || item, value = metrics.si_sdr_db ?? metrics.si_sdr;
        const row = element('tr'), name = element('td', (item.comparison_title ? item.comparison_title + ' · ' : '') + candidateLabel(item) + (item.category ? ' · ' + item.category : ''));
        const score = element('td'); score.append(element('span', formatNumber(value)));
        if (Number.isFinite(value)) {
          const track = element('div', null, 'benchmark-metric-track'), bar = element('span', null, 'benchmark-metric-bar');
          bar.style.width = Math.max(0, Math.min(100, (value - minimum) / (maximum - minimum) * 100)) + '%'; track.append(bar); score.append(track);
        }
        row.append(name, score, element('td', formatNumber(metrics.si_sdr_improvement_db ?? metrics.si_sdr_improvement)),
          element('td', formatNumber(metrics.alignment_error_samples ?? metrics.alignment_samples ?? metrics.alignment?.samples ?? metrics.technical?.alignment?.samples) + ' ' + tr('samples', 'campioni')), element('td', statusLabel(item.status)));
        body.append(row);
      }
      table.append(body); section.append(table, element('small', tr('Bar lengths compare the displayed measurements only; they are not professional quality thresholds. Undefined silent-reference metrics appear as —.',
        'Le barre confrontano soltanto le misure visualizzate: non rappresentano soglie di qualità professionale. Le metriche non definite su riferimenti silenziosi sono indicate con —.'))); return section;
    }

    function renderCampaign(data) {
      campaignPanel.replaceChildren();
      const campaign = data.campaign || data;
      campaignPanel.append(element('h3', campaign.title || campaign.id), element('p',
        `${campaign.kind === 'release' ? tr('Release validation', 'Validazione di rilascio') : tr('Experimental campaign', 'Campagna sperimentale')} · ${statusLabel(campaign.status)}`));
      const counts = campaign.counts || data.counts || {}, done = Number(counts.completed || 0) + Number(counts.failed || 0) + Number(counts.invalid || 0) + Number(counts.unavailable || 0);
      const total = Number(counts.total || 0), progress = element('progress'); progress.max = Math.max(1, total); progress.value = Math.min(done, total);
      progress.setAttribute('aria-label', tr('Completed benchmark cases', 'Casi benchmark conclusi'));
      campaignPanel.append(progress, element('p', total ? `${done}/${total}` : tr('Waiting for benchmark results.', 'In attesa dei risultati del benchmark.')));
      const actions = element('div', null, 'benchmark-actions');
      const run = button(tr('Run / resume pending cases', 'Esegui / riprendi casi pendenti'), task(async () => { await call(`/campaigns/${encodeURIComponent(campaignId)}/run`, {retry_failed: false}); await openCampaign(campaignId); }));
      run.disabled = ['running', 'queued'].includes(campaign.status); actions.append(run);
      const retry = button(tr('Retry failed cases', 'Riprova casi falliti'), task(async () => { await call(`/campaigns/${encodeURIComponent(campaignId)}/run`, {retry_failed: true}); await openCampaign(campaignId); }));
      retry.disabled = run.disabled; actions.append(retry);
      const exportLink = element('a', tr('Export reports, ratings and audio ZIP', 'Esporta report, valutazioni e audio ZIP'), 'utility-btn');
      exportLink.href = BASE + `/campaigns/${encodeURIComponent(campaignId)}/export`; exportLink.download = ''; actions.append(exportLink); campaignPanel.append(actions);
      campaignPanel.append(element('p', tr('Inferences not executed, unavailable models and missing real recordings remain explicit. Synthetic success cannot replace listening approval.',
        'Inferenze non eseguite, modelli indisponibili e registrazioni reali mancanti restano espliciti. Il successo su audio sintetico non sostituisce l’approvazione d’ascolto.'), 'benchmark-validation-note'));
      const cases = data.cases || campaign.cases || [];
      const caseOptions = select([['', tr('Select a listening case…', 'Seleziona un caso da ascoltare…')], ...cases.map(c => [c.id, [c.title || c.id, c.group, c.category].filter(Boolean).join(' · ')])], caseId || '');
      caseOptions.setAttribute('aria-label', tr('Listening case', 'Caso di ascolto'));
      caseOptions.addEventListener('change', task(async () => { if (caseOptions.value) await openCase(caseOptions.value); })); campaignPanel.append(field(tr('Blind listening', 'Ascolto cieco'), caseOptions));
      if (Array.isArray(data.manual_batch) && data.manual_batch.length) {
        const batch = element('div', null, 'benchmark-actions');
        campaignPanel.append(element('h4', tr('First guided listening batch', 'Primo batch guidato di ascolto')));
        for (const entry of data.manual_batch.slice(0, 10)) {
          const id = typeof entry === 'string' ? entry : entry.case_id || entry.id;
          const info = cases.find(item => item.id === id);
          if (id) batch.append(button(info?.title || id, task(() => openCase(id))));
        }
        campaignPanel.append(batch);
      }
      const results = data.public_blind_results || data.results || [];
      // Before ratings, only labels are rendered even if a privileged response
      // contains internal model IDs. The blind API must also omit identities.
      const groups = new Map();
      for (const row of results) { const group = row.group || row.case_group || tr('Unclassified', 'Non classificati'); if (!groups.has(group)) groups.set(group, []); groups.get(group).push(row); }
      for (const [group, rows] of groups) campaignPanel.append(renderMetrics(rows, tr('Measurements · ', 'Misure · ') + group));
      const categories = categoryRows(data.summary?.categories);
      if (categories.length) campaignPanel.append(renderMetrics(categories, tr('By category', 'Per categoria')));
      const comparePanel = element('section', null, 'benchmark-version-comparison');
      const compareActions = element('div', null, 'benchmark-actions');
      const otherCampaigns = savedCampaigns.filter(item => item.id !== campaignId);
      const comparison = select([['', tr('Choose a second campaign…', 'Scegli una seconda campagna…')], ...otherCampaigns.map(item => [item.id, item.title || item.id])]);
      comparison.setAttribute('aria-label', tr('Campaign or model version to compare', 'Campagna o versione del modello da confrontare'));
      const compare = button(tr('Compare campaign / model versions', 'Confronta campagne / versioni dei modelli'), task(async () => {
        if (!comparison.value) throw Error(tr('Choose a second campaign.', 'Scegli una seconda campagna.'));
        const selected = campaignId;
        const other = await call('/campaigns/' + encodeURIComponent(comparison.value));
        if (!alive() || campaignId !== selected) return;
        const otherInfo = other.campaign || other;
        const rows = [
          ...results.map(item => ({...item, comparison_title: campaign.title || campaign.id})),
          ...(other.public_blind_results || other.results || []).map(item => ({...item, comparison_title: otherInfo.title || otherInfo.id}))
        ];
        comparePanel.replaceChildren(renderMetrics(rows, tr('Campaign comparison', 'Confronto campagne')),
          element('small', tr('Compare the same cases, category options and metrics. A changed corpus or configuration is not an isolated model improvement. Model identities remain hidden until rated.',
            'Confronta gli stessi casi, opzioni delle categorie e metriche. Un corpus o una configurazione diversi non dimostrano un miglioramento del solo modello. Le identità rimangono nascoste fino alla valutazione.')));
      }));
      compare.disabled = !otherCampaigns.length; compareActions.append(comparison, compare); campaignPanel.append(compareActions, comparePanel);
      const completedRatings = data.ratings || [];
      const ratingsBox = element('details'); ratingsBox.append(element('summary', tr('Saved human assessments', 'Valutazioni umane salvate') + ` (${completedRatings.length})`));
      for (const rating of completedRatings) {
        const row = element('article', null, 'benchmark-saved-rating');
        row.append(element('strong', rating.case_id + ' · ' + (rating.label || rating.candidate_label || tr('Candidate', 'Candidato'))),
          element('p', SCORE_KEYS.map(key => `${label(SCORE_LABELS[key])}: ${rating.scores?.[key] ?? '—'}`).join(' · ')),
          element('p', ({professional: tr('Acceptable for professional use', 'Accettabile per uso professionale'), limited: tr('Acceptable with limitations', 'Accettabile con limitazioni'), rejected: tr('Not acceptable', 'Non accettabile')})[rating.decision] || rating.decision),
          element('p', rating.comment || ''));
        if (rating.identity?.name) row.append(element('code', [rating.identity.name, rating.identity.version, rating.identity.checkpoint_sha256].filter(Boolean).join(' · ')));
        ratingsBox.append(row);
      }
      campaignPanel.append(ratingsBox);
      const approval = data.approval;
      if (approval) {
        const approvalCampaign = campaignId;
        const review = element('section', null, 'benchmark-final-approval');
        review.append(element('h4', tr('Final campaign approval', 'Approvazione finale della campagna')),
          element('p', statusLabel(approval.state || 'awaiting_human_validation')));
        if (approval.approved === true || ['approved', 'manually_approved', 'approved_manually'].includes(approval.state)) {
          review.append(element('p', tr('Explicit approval recorded for the exact model, corpus, pipeline and output configuration. Relevant changes require a new validation.',
            'Approvazione esplicita registrata per l’esatta configurazione di modello, corpus, pipeline e output. Modifiche rilevanti richiedono una nuova validazione.')));
          if (approval.configuration_sha256) review.append(element('code', approval.configuration_sha256));
        } else if (approval.can_approve === true && approval.configuration_sha256) {
          const consent = element('input'); consent.type = 'checkbox';
          const comment = element('textarea'); comment.rows = 3; comment.maxLength = 4000;
          const approve = button(tr('Record explicit final approval', 'Registra approvazione finale esplicita'), task(async () => {
            if (!consent.checked) throw Error(tr('Explicit listening confirmation is required.', 'È richiesta una conferma esplicita dell’ascolto.'));
            approve.disabled = true;
            try {
              await call(`/campaigns/${encodeURIComponent(approvalCampaign)}/approve`, {confirm: true,
                configuration_sha256: approval.configuration_sha256, comment: comment.value.trim()});
              if (campaignId === approvalCampaign) await openCampaign(approvalCampaign);
            } finally { approve.disabled = !consent.checked; }
          }), 'utility-btn primary');
          approve.disabled = true;
          consent.addEventListener('change', () => { approve.disabled = !consent.checked; });
          review.append(field(tr('I completed the listening tests and explicitly approve this exact campaign configuration for professional use.',
            'Ho completato le prove d’ascolto e approvo esplicitamente questa esatta configurazione della campagna per uso professionale.'), consent),
            element('code', approval.configuration_sha256), field(tr('Final review notes', 'Note della revisione finale'), comment), approve);
        } else {
          review.append(element('p', tr('Final approval is blocked until the complete release benchmark, required corpus and human assessments satisfy the server criteria.',
            'Approvazione finale bloccata finché benchmark completo di rilascio, corpus richiesto e valutazioni umane non soddisfano i criteri del server.')));
          for (const reason of approval.blocked_reasons || []) review.append(element('p', reason));
        }
        campaignPanel.append(review);
      }
    }

    async function openCampaign(id) {
      const selected = String(id);
      if (campaignId !== selected) { caseId = null; blindData = null; selectedAudio = null; audio.pause(); listeningPanel.replaceChildren(); }
      campaignId = selected; generation++;
      const token = generation; clearTimeout(timer); timer = null;
      const data = await call('/campaigns/' + encodeURIComponent(selected));
      if (!alive() || campaignId !== selected || generation !== token) return;
      campaignData = data; renderCampaign(data);
      if (['running', 'queued'].includes((data.campaign || data).status)) {
        timer = setTimeout(() => { if (alive() && campaignId === selected) openCampaign(selected).catch(fail); }, 2000);
      }
    }

    async function openCase(id) {
      if (!campaignId) return;
      caseId = String(id); const selectedCampaign = campaignId, selectedCase = caseId; playbackGeneration++;
      audio.pause();
      const data = await call(`/campaigns/${encodeURIComponent(campaignId)}/blind?case_id=${encodeURIComponent(caseId)}`);
      if (!alive() || campaignId !== selectedCampaign || caseId !== selectedCase) return;
      blindData = data; selectedAudio = null; audio.removeAttribute('src'); audio.load(); listeningPanel.replaceChildren();
      const item = data.case || {};
      listeningPanel.append(element('h3', item.title || item.id || caseId), element('p', [item.category, item.description].filter(Boolean).join(' · ')),
        element('p', tr('Blind comparison: model names remain concealed until that candidate has been rated. Contamination: 5 means negligible bleed.',
          'Confronto cieco: i nomi dei modelli restano nascosti fino alla valutazione del singolo candidato. Contaminazione: 5 indica interferenza trascurabile.')));
      const choices = element('div', null, 'benchmark-ab-choices');
      if (data.input_url) choices.append(button(tr('Original DRUMS', 'DRUMS originale'), task(() => play({label: tr('Original DRUMS', 'DRUMS originale'), audio_url: data.input_url, peaks: data.input_peaks}))));
      if (data.reference_url) choices.append(button(tr('Percussion reference', 'Riferimento percussioni'), task(() => play({label: tr('Reference', 'Riferimento'), audio_url: data.reference_url, peaks: data.reference_peaks}))));
      for (const candidate of data.candidates || []) choices.append(button(candidate.label, task(() => play(candidate)), 'utility-btn benchmark-ab'));
      listeningPanel.append(choices, playback);
      if (!(data.candidates || []).length) listeningPanel.append(element('p', tr('No technically valid model output is available for this case. Run an installed, authorized candidate first.',
        'Nessun output tecnicamente valido disponibile per questo caso. Esegui prima un candidato installato e autorizzato.')));
      for (const candidate of data.candidates || []) renderRating(candidate);
    }

    function renderRating(candidate) {
      const ratingCampaign = campaignId, ratingCase = caseId;
      const form = element('form', null, 'benchmark-rating');
      form.append(element('h4', candidate.label));
      const controls = {}, scores = element('div', null, 'benchmark-score-grid');
      for (const key of SCORE_KEYS) {
        controls[key] = select([['', tr('Choose…', 'Scegli…')], ...[1, 2, 3, 4, 5].map(n => [String(n), String(n)])]);
        controls[key].required = true; scores.append(field(label(SCORE_LABELS[key]), controls[key]));
      }
      const decision = select([['', tr('Choose…', 'Scegli…')], ['professional', tr('Acceptable for professional use', 'Accettabile per uso professionale')],
        ['limited', tr('Acceptable with limitations', 'Accettabile con limitazioni')], ['rejected', tr('Not acceptable', 'Non accettabile')]]);
      decision.required = true;
      const professionalConsent = element('input'); professionalConsent.type = 'checkbox'; professionalConsent.disabled = true;
      const professionalConsentRow = field(tr('After listening, I explicitly confirm this exact excerpt is acceptable for professional use. This does not approve the whole campaign.',
        'Dopo l’ascolto, confermo esplicitamente che questo esatto estratto è accettabile per uso professionale. La conferma non approva l’intera campagna.'), professionalConsent);
      professionalConsentRow.classList.add('benchmark-professional-consent'); professionalConsentRow.hidden = true;
      decision.addEventListener('change', () => {
        const professional = decision.value === 'professional';
        professionalConsent.checked = false; professionalConsent.disabled = !professional; professionalConsent.required = professional;
        professionalConsentRow.hidden = !professional;
      });
      const comment = element('textarea'); comment.rows = 3; comment.maxLength = 4000;
      const saved = element('p', '', 'benchmark-rating-state'); saved.setAttribute('role', 'status');
      const submit = element('button', tr('Save this assessment', 'Salva questa valutazione'), 'utility-btn primary'); submit.type = 'submit';
      form.append(scores, field(tr('Final assessment of this excerpt', 'Valutazione finale di questo estratto'), decision),
        professionalConsentRow, field(tr('Notes and defects to investigate', 'Note e difetti da approfondire'), comment), submit, saved);
      if (candidate.rated) saved.textContent = tr('Assessment already saved. A new submission records an updated assessment.', 'Valutazione già salvata. Un nuovo invio registra una valutazione aggiornata.');
      form.addEventListener('submit', task(async event => {
        event.preventDefault();
        const values = validateRating({scores: Object.fromEntries(SCORE_KEYS.map(key => [key, controls[key].value])), decision: decision.value,
          comment: comment.value, explicit_approval: professionalConsent.checked && !professionalConsent.disabled});
        submit.disabled = true;
        try {
          const response = await call(`/campaigns/${encodeURIComponent(ratingCampaign)}/ratings`, {case_id: ratingCase, candidate_id: candidate.candidate_id, ...values});
          if (!alive() || campaignId !== ratingCampaign || caseId !== ratingCase) return;
          candidate.rated = true;
          professionalConsent.checked = false;
          saved.textContent = tr('Saved against the exact output and campaign configuration. Campaign approval remains separate.', 'Salvata sull’output e sulla configurazione esatti. L’approvazione della campagna rimane separata.');
          if (response.identity) {
            const identity = response.identity;
            form.append(element('p', tr('Rated candidate: ', 'Candidato valutato: ') + (identity.name || ''), 'benchmark-revealed'),
              element('code', [identity.version, identity.checkpoint_sha256].filter(Boolean).join(' · ')));
          }
          if (response.binding) {
            for (const key of ['output_sha256', 'configuration_sha256', 'corpus_sha256']) {
              if (response.binding[key]) form.append(element('code', key + ': ' + response.binding[key]));
            }
          }
          await openCampaign(ratingCampaign);
        } finally { submit.disabled = false; }
      }));
      listeningPanel.append(form);
    }

    const dispose = () => {
      disposed = true; playbackGeneration++; clearTimeout(timer); controller.abort(); audio.pause(); audio.removeAttribute('src'); audio.load();
      if (host._mtaBenchmarkDispose === dispose) delete host._mtaBenchmarkDispose;
    };
    host._mtaBenchmarkDispose = dispose;
    return {load: async () => { status.textContent = tr('Loading benchmark catalog…', 'Caricamento catalogo benchmark…'); await loadCatalog(); await loadCampaigns(); if (alive()) status.textContent = tr('Ready. Human validation pending until recorded listening and explicit final approval.', 'Pronto. Validazione umana in attesa fino all’ascolto registrato e all’approvazione finale esplicita.'); },
      openCampaign, openCase, dispose, fail, get campaign() { return campaignData; }};
  }

  let currentView = null;
  async function open(host) {
    currentView?.dispose();
    if (!host) {
      if (typeof showUtilityModal !== 'function') throw Error('MTA modal host unavailable');
      showUtilityModal(tr('AI benchmark and validation', 'Benchmark e validazione AI'), '<div id="mtaBenchmarkHost"></div>');
      host = document.getElementById('mtaBenchmarkHost');
    }
    if (!host) throw Error('MTA benchmark host unavailable');
    host._mtaBenchmarkDispose?.(); currentView = createView(host);
    try { await currentView.load(); } catch (error) { currentView.fail(error); }
    return currentView;
  }
  window.MtaBenchmark = {open, close: () => { currentView?.dispose(); currentView = null; }};
  // Small production helpers are exported for offline regression and reuse.
  window.MtaBenchmark.helpers = {validateRating, candidateLabel, safeAudioUrl, excerptBounds, switchPosition, statusLabel, drawWaveform, categoryRows};
})();
