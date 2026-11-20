// Live view: one server-sent event stream feeds the status panel, the front-desk feed,
// the roster, and the 3D room.
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const token = new URLSearchParams(location.search).get('token');
  const has3d = window.BmaRoom && window.BmaRoom.init($('#stage'), $('#scene'), $('#layer'));
  if (!has3d) { $('#no3d').hidden = false; $('#scene').hidden = true; }
  const room = has3d ? window.BmaRoom : { setAgents() {}, setLead() {}, setStatus() {}, setHeavy() {}, setPreview() {} };

  let lastHeavy = { running: 0, waiting: 0 }, lastState = null, gotSnapshot = false;

  // ---------- connection ----------
  function conn(state, label) { const c = $('#conn'); c.dataset.state = state; c.querySelector('span').textContent = label; }
  if (!token) {
    conn('down', 'No token');
    $('#phase-line').textContent = 'Open the link that /build-my-app:ui printed. It carries the access token.';
    return;
  }
  const es = new EventSource(`/events?token=${encodeURIComponent(token)}`);
  es.addEventListener('open', () => conn('live', 'Live'));
  es.addEventListener('error', () => conn(es.readyState === 2 ? 'down' : 'connecting', es.readyState === 2 ? 'Disconnected' : 'Reconnecting'));
  es.addEventListener('snapshot', (m) => {
    const d = JSON.parse(m.data);
    renderState(d.state);
    $('#feed').innerHTML = ''; seen.clear();
    (d.feed || []).forEach(addFeed);
    renderAgents(d, !gotSnapshot);
    perms = d.perms || [];
    questions = d.questions || [];
    renderPreviews(d.previews || []);
    renderBridge(d.bridge);
    gotSnapshot = true;
    if (!(d.feed || []).length) emptyFeed();
  });
  es.addEventListener('state', (m) => renderState(JSON.parse(m.data)));
  es.addEventListener('agents', (m) => renderAgents(JSON.parse(m.data), false));
  es.addEventListener('feed', (m) => addFeed(JSON.parse(m.data)));
  es.addEventListener('bridge', (m) => renderBridge(JSON.parse(m.data)));
  es.addEventListener('perms', (m) => { perms = JSON.parse(m.data); renderTray(); });
  es.addEventListener('questions', (m) => { questions = JSON.parse(m.data); renderTray(); });
  es.addEventListener('previews', (m) => renderPreviews(JSON.parse(m.data)));
  es.addEventListener('chat_status', (m) => { const d = JSON.parse(m.data); setChatStatus(d.chat_id, d.status); });

  // ---------- status ----------
  function kv(list, rows) {
    list.innerHTML = '';
    rows.filter((r) => r[1] !== undefined && r[1] !== null && r[1] !== '').forEach(([k, v, cls]) => {
      const li = el('li'); li.append(el('span', null, k), el('span', cls || null, String(v))); list.append(li);
    });
  }
  function short(v) {
    if (v == null) return '';
    if (typeof v === 'string') return v;
    if (Array.isArray(v)) return v.map(short).join(', ');
    if (typeof v === 'object') return Object.entries(v).map(([k, x]) => `${k} ${short(x)}`).join(' · ');
    return String(v);
  }
  function renderState(st) {
    if (!st) return;
    if (st.error) { $('#phase-line').textContent = st.error; return; }
    lastState = st;
    $('#project').textContent = st.project || 'build-my-app';
    document.title = `${st.project} · build-my-app`;
    const cur = st.phases.find((p) => p.id === st.current);
    $('#phase-line').textContent = cur
      ? `Phase ${cur.title}${cur.step ? ' — ' + cur.step : ''}`
      : st.next.length ? `Ready to start: ${st.next.join(', ')}` : 'All phases done';
    const rail = $('#rail'); rail.innerHTML = '';
    st.phases.forEach((p) => {
      const li = el('li', p.status);
      const label = { done: 'done', in_progress: 'in progress', gate: 'at gate', pending: '' }[p.status] || '';
      li.append(el('span', 'd'), el('span', null, p.title), el('span', 's', label));
      rail.append(li);
    });
    $('#step').textContent = cur && cur.status === 'gate' ? 'Waiting for your approval at this gate.' : '';
    const ds = st.decisions || [];
    $('#decisions-box').hidden = !ds.length;
    const dl = $('#decisions'); dl.innerHTML = '';
    ds.forEach((d) => {
      const li = el('li');
      li.append(el('div', null, `${d.id} · ${d.question}`));
      const opts = (d.options || []).join(' / ');
      if (opts || d.recommendation) li.append(el('div', 'rec', [opts, d.recommendation ? `recommended: ${d.recommendation}` : ''].filter(Boolean).join(' · ')));
      dl.append(li);
    });
    const loops = st.loops || [];
    $('#loops-box').hidden = !loops.length;
    kv($('#loops'), loops.map((l) => [l.name, `round ${l.round} of ${l.max}`]));
    renderMachine();
    const env = st.environment || {};
    kv($('#env'), [
      ['Autonomy', st.autonomy], ['Branch', st.branch], ['Stack', short(st.stack)], ['Design tool', short(st.design_tool)],
      ...Object.entries(env).slice(0, 10).map(([k, v]) => [k, short(v)]),
    ]);
    room.setStatus(st);
    renderTray();
  }
  function renderMachine() {
    const r = (lastState && lastState.resources) || {};
    const pressure = r.pressure || 'unknown';
    kv($('#machine'), [
      ['Memory', r.memory_gb ? `${r.memory_gb} GB` : ''],
      ['Cores', r.cpus],
      ['Pressure', pressure, pressure === 'normal' ? '' : `pressure-${pressure}`],
      ['Heavy runs', r.heavy_slots ? `${lastHeavy.running} of ${r.heavy_slots} in use${lastHeavy.waiting ? `, ${lastHeavy.waiting} waiting` : ''}` : ''],
      ['Test workers', r.test_workers],
    ]);
  }

  // ---------- agents ----------
  function renderAgents(d, initial) {
    const agents = d.agents || [];
    lastHeavy = d.heavy || lastHeavy;
    renderMachine();
    room.setHeavy(lastHeavy.running);
    room.setAgents(agents, initial);
    const a = d.assistant || {};
    if (a.now && Date.now() / 1000 - a.ts < 60) room.setLead(a.now);

    const live = agents.filter((x) => x.status !== 'done');
    const done = agents.filter((x) => x.status === 'done').slice(-6).reverse();
    $('#heavy').textContent = live.length ? `${live.length} working now` : '';
    const ul = $('#roster'); ul.innerHTML = '';
    if (!agents.length) { ul.append(el('li', 'empty', 'No agents yet. They appear here when Claude hands out work.')); return; }
    [...live, ...done].forEach((x) => {
      const li = el('li');
      const sw = el('span', 'sw'); sw.style.background = window.bmaCast(x.type).color;
      li.append(sw, el('span', 'name', x.type), el('span', `pill ${x.status}`, x.status));
      li.append(el('span', 'now', (x.status === 'done' ? x.result : x.now) || x.desc || ''));
      ul.append(li);
    });
  }

  // ---------- feed ----------
  const seen = new Set();
  function emptyFeed() {
    $('#feed').append(el('li', 'empty', 'Nothing yet. Talk to Claude here or in the terminal: both sides of the conversation and agent updates show up here.'));
  }
  function hhmm(ts) { return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  function addFeed(item) {
    const key = `${item.ts}|${item.who}|${item.text}`;
    if (seen.has(key)) return;
    seen.add(key);
    const feed = $('#feed');
    const empty = feed.querySelector('.empty'); if (empty) empty.remove();
    const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 60;
    const kind = item.who === 'you' ? 'you' : item.who === 'assistant' ? 'assistant' : item.who === 'system' ? 'system' : 'agent';
    const li = el('li', kind + (item.kind === 'note' && kind === 'assistant' ? ' note' : ''));
    const who = el('div', 'who');
    who.append(el('b', null, { you: 'You', assistant: window.bmaCast('assistant').name, system: 'Note' }[kind] || item.who));
    if (item.via) who.append(el('span', 'badge', item.via === 'terminal' ? '⌨ terminal' : item.via === 'web' ? '🌐 web' : `✉ ${item.via}`));
    who.append(el('span', null, hhmm(item.ts)));
    if (item.kind === 'done' && item.outcome) {
      who.append(el('span', 'badge outcome ' + item.outcome, { pass: '✓ pass', fixes: '● needs fixes', blocked: '✕ blocked' }[item.outcome]));
    }
    if (item.kind === 'done' && item.agent) li.dataset.report = item.agent;
    li.append(who, el('div', 'msg', item.text));
    if (item.chat_id) {
      li.dataset.chat = item.chat_id;
      li.append(el('span', 'st'));
      paintStatus(li, item.status);
    }
    feed.append(li);
    while (feed.children.length > 200) feed.firstChild.remove();
    if (nearBottom) feed.scrollTop = feed.scrollHeight;
    if (item.who === 'assistant') room.setLead(firstSentence(item.text));
    if (item.who === 'you' && item.via === 'web') room.setLead('Got your message. One moment…');
  }
  // ---------- chat ----------
  const STATUS = { sent: 'Sent', delivered: 'Delivered to Claude', seen: 'Claude is on it', quiet: 'No reaction from Claude yet' };
  function paintStatus(li, status) {
    const st = li.querySelector('.st');
    if (!st) return;
    st.textContent = STATUS[status] || '';
    st.className = 'st ' + (status || '');
  }
  function setChatStatus(id, status) {
    const li = document.querySelector(`#feed li[data-chat="${CSS.escape(id)}"]`);
    if (li) paintStatus(li, status);
  }
  let chatOn = false;
  function renderBridge(b) {
    b = b || { sessions: 0, chat: 0 };
    chatOn = b.chat > 0;
    const input = $('#chat-input'), note = $('#chat-note');
    input.disabled = !chatOn;
    input.placeholder = chatOn ? 'Message Claude. Enter sends, Shift+Enter adds a line.' : 'Chat is off. See the note below.';
    $('#send').disabled = !chatOn || !input.value.trim();
    note.hidden = chatOn;
    renderTray();
    $('#chat-note-text').textContent = b.sessions
      ? 'Claude Code is running, but without chat. To chat from this page, restart it in this project with:'
      : 'No Claude Code session has checked in. If one is running here, run /mcp in it and check that the "bma" server is connected; otherwise start one in this project with:';
  }
  const input = $('#chat-input');
  function grow() {  // fit the box to its text, from one line up to the CSS max-height
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight + 2, 148) + 'px';
  }
  input.addEventListener('input', () => { grow(); $('#send').disabled = !chatOn || !input.value.trim(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('#chat').requestSubmit(); }
  });
  $('#chat').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || !chatOn) return;
    const err = $('#chat-error'); err.hidden = true;
    $('#send').disabled = true;
    try {
      const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Token': token },
        body: JSON.stringify({ text }) });
      if (!r.ok) throw new Error(await r.text() || `Sending failed (${r.status}).`);
      input.value = '';
      grow();
    } catch (ex) {
      err.textContent = ex.message; err.hidden = false;
    } finally {
      $('#send').disabled = !chatOn || !input.value.trim();
      input.focus();
    }
  });
  $('#copy-cmd').addEventListener('click', async () => {
    const btn = $('#copy-cmd');
    try { await navigator.clipboard.writeText($('#chat-cmd').textContent); btn.textContent = 'Copied'; }
    catch (ex) { const r = document.createRange(); r.selectNodeContents($('#chat-cmd')); getSelection().removeAllRanges(); getSelection().addRange(r); btn.textContent = 'Selected'; }
    setTimeout(() => (btn.textContent = 'Copy'), 1500);
  });

  // ---------- preview: try the app ----------
  let previews = [];
  const PV_KIND = { web: 'Web', api: 'API', ios: 'iOS Simulator', android: 'Android emulator' };
  const PV_STATE = { running: 'ready', stopped: 'stopped', 'simulator off': 'simulator off', 'emulator off': 'emulator off',
    'not installed': 'not installed', 'no Xcode tools': 'no Xcode', 'no Android tools': 'no adb' };
  const localUrl = (u) => /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(\/|$)/.test(u || '');
  async function openPreview(p) {
    const err = $('#pv-error'); err.hidden = true;
    if (p.kind === 'web' || p.kind === 'api') {
      if (localUrl(p.target)) window.open(p.target, '_blank', 'noopener,noreferrer');
      return;
    }
    try {
      const r = await fetch('/api/preview', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Token': token },
        body: JSON.stringify({ id: p.id, action: 'open' }) });
      if (!r.ok) throw new Error(await r.text() || `Couldn't open it (${r.status}).`);
    } catch (ex) { err.textContent = ex.message; err.hidden = false; }
  }
  async function refreshShot(p, btn) {
    btn.disabled = true;
    try {
      await fetch('/api/preview', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Token': token },
        body: JSON.stringify({ id: p.id, action: 'shot' }) });
    } finally { btn.disabled = false; }
  }
  function restartText(p) {
    return `Please restart the preview "${p.label}"` + (p.cmd ? ` (it was started with \`${p.cmd}\`)` : '') + ' and record it again.';
  }
  if (has3d) window.BmaRoom.onPreview = (p) => openPreview(p);
  if (has3d) window.BmaRoom.onReport = (aid) => {   // a folder in the room's tray was clicked: show that report
    const li = [...document.querySelectorAll('#feed li[data-report]')].find((x) => x.dataset.report === aid);
    if (!li) return;
    li.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    li.classList.remove('flash'); void li.offsetWidth; li.classList.add('flash');
  };
  function renderPreviews(list) {
    previews = list || [];
    const box = $('#preview-box'), ul = $('#previews');
    box.hidden = !previews.length;
    ul.innerHTML = '';
    previews.forEach((p) => {
      const live = p.state === 'running';
      const li = el('li', 'pv');
      const head = el('div', 'head');
      head.append(el('b', null, p.label), el('span', 'st' + (live ? ' running' : ''), PV_STATE[p.state] || p.state));
      li.append(head, el('div', 'meta', [PV_KIND[p.kind] || p.kind, p.target, p.commit].filter(Boolean).join(' · ')));
      if (p.shot) {
        const b = el('button', 'shot'); b.type = 'button'; b.title = live ? 'Open the app' : 'Last screenshot';
        b.setAttribute('aria-label', live ? `Open ${p.label}` : `Last screenshot of ${p.label}`);
        const img = document.createElement('img');
        img.alt = ''; img.src = `/api/preview-shot?token=${encodeURIComponent(token)}&id=${encodeURIComponent(p.id)}&v=${p.shot}`;
        img.style.cssText = 'display:block;width:100%;max-height:220px;object-fit:contain;border-radius:8px';
        b.append(img); b.disabled = !live; b.addEventListener('click', () => openPreview(p));
        li.append(b);
      }
      const acts = el('div', 'acts');
      if (live && (p.kind === 'web' || p.kind === 'api') && localUrl(p.target)) {
        const a = el('a', 'primary', 'Open app ↗'); a.href = p.target; a.target = '_blank'; a.rel = 'noopener noreferrer';
        acts.append(a);
      } else if (live) {
        const b = el('button', 'primary', 'Open app'); b.type = 'button'; b.addEventListener('click', () => openPreview(p));
        acts.append(b);
      } else {
        const b = el('button', null, 'Ask Claude to restart…'); b.type = 'button';
        b.addEventListener('click', () => {
          if (chatOn) draft(restartText(p));
          else { const err = $('#pv-error'); err.textContent = 'Chat is off: ask Claude in the terminal to restart the preview.'; err.hidden = false; }
        });
        acts.append(b);
      }
      if (live && (p.kind === 'ios' || p.kind === 'android')) {
        const b = el('button', null, 'Refresh screenshot'); b.type = 'button';
        b.addEventListener('click', () => refreshShot(p, b));
        acts.append(b);
      }
      li.append(acts);
      ul.append(li);
    });
    const main = previews.find((p) => p.state === 'running') || previews[0] || null;
    room.setPreview(main && { ...main, live: main.state === 'running',
      img: main.shot ? `/api/preview-shot?token=${encodeURIComponent(token)}&id=${encodeURIComponent(main.id)}&v=${main.shot}` : null });
    renderTray();
  }

  // ---------- colors ----------
  const pal = $('#palette');
  Object.entries(window.BMA_PALETTES || {}).forEach(([k, v]) => {
    const o = document.createElement('option'); o.value = k; o.textContent = v.label; pal.append(o);
  });
  pal.value = window.BMA_PALETTE;
  pal.addEventListener('change', () => window.bmaSetPalette(pal.value));

  // ---------- presence: lets Claude's questions come here while you're looking at the page ----------
  let outdatedShown = false;
  function ping() {
    fetch('/api/presence', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Token': token },
      body: JSON.stringify({ visible: document.visibilityState === 'visible' }) }).then((r) => {
      if (r.status === 404 && !outdatedShown) {   // an older server that doesn't know this page
        outdatedShown = true;
        addFeed({ ts: Date.now() / 1000, who: 'system', text: 'This page\'s server is out of date, so Claude\'s questions '
          + 'can\'t come here. Run /build-my-app:ui in Claude Code to restart it, then open the new link.' });
      }
    }).catch(() => {});
  }
  document.addEventListener('visibilitychange', ping);
  setInterval(ping, 15000);
  ping();

  // ---------- "needs you" tray ----------
  let perms = [], questions = [], trayDirty = false;
  $('#tray').addEventListener('focusout', () => setTimeout(() => { if (trayDirty && !$('#tray').contains(document.activeElement)) renderTray(); }, 0));
  const drafts = {};  // qid → {question text → chosen labels / other text}, kept across re-renders
  function terminalQuestionCard(q) {   // waiting in the terminal: shown so the page never misses a question
    const c = el('div', 'card ask terminal');
    c.append(el('div', 't', q.questions.length > 1 ? `Claude asks ${q.questions.length} questions in the terminal` : 'Claude asks in the terminal'));
    q.questions.forEach((x) => {
      const fs = el('div', 'tq');
      const lg = el('div', 'q');
      if (x.header) lg.append(el('span', 'chip', x.header));
      lg.append(document.createTextNode(x.question));
      fs.append(lg);
      const ul = el('ul', 'tq-opts');
      (x.options || []).forEach((o) => {
        const li = el('li');
        li.append(el('b', null, o.label));
        if (o.description) li.append(el('small', null, ' ' + o.description));
        ul.append(li);
      });
      fs.append(ul);
      c.append(fs);
    });
    c.append(el('div', 'hint', 'Answer it in the terminal. Questions come to this page instead when it is on screen as Claude asks.'));
    return c;
  }
  function questionCard(q) {
    if (q.state === 'terminal') return terminalQuestionCard(q);
    const c = el('form', 'card ask');
    const state = drafts[q.qid] || (drafts[q.qid] = {});
    c.append(el('div', 't', q.questions.length > 1 ? `Claude asks you ${q.questions.length} questions` : 'Claude asks'));
    q.questions.forEach((x, qi) => {
      const st = state[x.question] || (state[x.question] = { picked: [], other: '' });
      const fs = el('fieldset');
      const lg = el('legend');
      if (x.header) lg.append(el('span', 'chip', x.header));
      lg.append(document.createTextNode(x.question));
      fs.append(lg);
      const name = `${q.qid}-${qi}`;
      (x.options || []).forEach((o) => {
        const lab = el('label', 'opt');
        const inp = document.createElement('input');
        inp.type = x.multiSelect ? 'checkbox' : 'radio';
        inp.name = name; inp.value = o.label;
        inp.checked = st.picked.includes(o.label);
        inp.addEventListener('change', () => {
          st.picked = x.multiSelect ? [...fs.querySelectorAll('input:checked')].map((i) => i.value).filter((v) => v !== '__other')
                                    : [o.label];
          if (!x.multiSelect) { st.other = ''; const t = fs.querySelector('.other'); if (t) t.value = ''; }
          sync();
        });
        const txt = el('span');
        txt.append(el('b', null, o.label));
        if (o.description) txt.append(el('small', null, o.description));
        lab.append(inp, txt);
        fs.append(lab);
      });
      const other = document.createElement('input');
      other.type = 'text'; other.className = 'other'; other.placeholder = 'Other: type your own answer';
      other.setAttribute('aria-label', `Other answer to: ${x.question}`);
      other.value = st.other;
      other.addEventListener('input', () => {
        st.other = other.value;
        if (!x.multiSelect && other.value.trim()) { st.picked = []; fs.querySelectorAll('input[type=radio]').forEach((i) => (i.checked = false)); }
        sync();
      });
      fs.append(other);
      c.append(fs);
    });
    const acts = el('div', 'acts');
    const send = el('button', 'primary', 'Send answer'); send.type = 'submit';
    const term = button('Answer in the terminal', null, () => submit({ terminal: true }));
    term.disabled = false;
    acts.append(send, term);
    const err = el('div', 'err'); err.hidden = true;
    c.append(acts, el('div', 'hint', 'Claude is waiting for this answer. The terminal shows the question only if you move it there.'), err);
    function answers() {
      const out = {};
      for (const x of q.questions) {
        const st = state[x.question];
        const parts = [...st.picked, ...(st.other.trim() ? [st.other.trim()] : [])];
        if (!parts.length) return null;
        out[x.question] = parts.join(', ');
      }
      return out;
    }
    function sync() { send.disabled = !answers(); }
    async function submit(body) {
      c.querySelectorAll('button, input').forEach((b) => (b.disabled = true));
      err.hidden = true;
      try {
        const r = await fetch('/api/answer', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Token': token },
          body: JSON.stringify({ qid: q.qid, ...body }) });
        if (!r.ok) throw new Error(await r.text() || `Failed (${r.status}).`);
        delete drafts[q.qid];
        questions = questions.filter((x) => x.qid !== q.qid);
        renderTray();
      } catch (ex) {
        err.textContent = ex.message; err.hidden = false;
        c.querySelectorAll('button, input').forEach((b) => (b.disabled = false));
        sync();
      }
    }
    c.addEventListener('submit', (e) => { e.preventDefault(); const a = answers(); if (a) submit({ answers: a }); });
    sync();
    return c;
  }
  function button(text, cls, onClick) {
    const b = el('button', cls, text);
    b.type = 'button';
    b.disabled = !chatOn;
    b.addEventListener('click', onClick);
    return b;
  }
  function draft(text) {  // put an answer in the chat box for the user to check and send
    input.value = text;
    input.focus();
    input.setSelectionRange(text.length, text.length);
    grow();
    $('#send').disabled = !chatOn || !input.value.trim();
  }
  async function answer(card, p, behavior) {
    card.querySelectorAll('button').forEach((b) => (b.disabled = true));
    const err = card.querySelector('.err');
    try {
      const r = await fetch('/api/permission', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Token': token },
        body: JSON.stringify({ request_id: p.request_id, behavior }) });
      if (!r.ok) throw new Error(await r.text() || `Failed (${r.status}).`);
      card.querySelector('.hint').textContent = behavior === 'allow' ? 'Allowed. Sending…' : 'Denied. Sending…';
    } catch (ex) {
      err.textContent = ex.message; err.hidden = false;
      card.querySelectorAll('button').forEach((b) => (b.disabled = !chatOn || (b.dataset.allow && p.hard)));
    }
  }
  function previewText(raw) {  // show the command or the file, not the JSON around it
    try {
      const o = JSON.parse(raw);
      if (o && typeof o.command === 'string') return '$ ' + o.command;
      if (o && typeof o.file_path === 'string') {
        const body = o.content || o.new_string || '';
        return o.file_path + (body ? '\n\n' + String(body).slice(0, 600) : '');
      }
    } catch (ex) { /* not JSON (or clipped): show as is */ }
    return raw;
  }
  function permCard(p) {
    const c = el('div', 'card perm' + (p.hard ? ' hard' : ''));
    c.append(el('div', 't', p.hard ? 'Hard stop · approval' : 'Approval'), el('div', 'q', `Claude wants to use ${p.tool}${p.desc ? ': ' + p.desc : ''}`));
    if (p.preview) c.append(el('pre', null, previewText(p.preview)));
    if (p.hard) c.append(el('div', 'why', `${p.reason || 'Hard stop.'} Allow it in the terminal; you can deny it here.`));
    const acts = el('div', 'acts');
    const allow = button('Allow once', 'primary', () => answer(c, p, 'allow'));
    allow.dataset.allow = '1';
    if (p.hard) allow.disabled = true;
    acts.append(allow, button('Deny', null, () => answer(c, p, 'deny')));
    const err = el('div', 'err'); err.hidden = true;
    c.append(acts, el('div', 'hint', p.refused ? 'Refused: hard stops are allowed only in the terminal.' : 'The terminal shows the same prompt; the first answer counts.'), err);
    return c;
  }
  function renderTray() {
    const tray = $('#tray');
    if (!tray) return;
    if (tray.contains(document.activeElement) && document.activeElement.closest('.ask')) { trayDirty = true; return; }  // don't steal focus mid-answer
    trayDirty = false;
    tray.innerHTML = '';
    questions.forEach((q) => tray.append(questionCard(q)));
    perms.forEach((p) => tray.append(permCard(p)));
    const st = lastState;
    const gate = st && st.phases && st.phases.find((p) => p.id === st.current && p.status === 'gate');
    if (gate) {
      const c = el('div', 'card');
      c.append(el('div', 't', 'Gate'), el('div', 'q', `${gate.title} is ready for your approval.`));
      const acts = el('div', 'acts');
      const live = previews.find((p) => p.state === 'running');
      if (live) { const t = button('Try the app first ↗', null, () => openPreview(live)); t.disabled = false; acts.append(t); }
      acts.append(button('Approve…', 'primary', () => draft(`I approve the ${gate.title} gate.`)),
        button('Ask for changes…', null, () => draft(`Before I approve the ${gate.title} gate, please change: `)));
      c.append(acts, el('div', 'hint', 'Puts your answer in the chat box to check and send.'));
      tray.append(c);
    }
    ((st && st.decisions) || []).forEach((d) => {
      const c = el('div', 'card');
      c.append(el('div', 't', `Decision ${d.id}${d.kind ? ' · ' + d.kind : ''}`), el('div', 'q', d.question));
      const acts = el('div', 'acts');
      (d.options || []).forEach((o) => acts.append(button(o, o === d.recommendation ? 'rec' : null, () => draft(`${d.id}: I choose "${o}".`))));
      if (!(d.options || []).length && d.recommendation) acts.append(button(`Go with: ${d.recommendation}`, 'rec', () => draft(`${d.id}: go with your recommendation (${d.recommendation}).`)));
      acts.append(button('Other…', null, () => draft(`${d.id}: `)));
      c.append(acts);
      tray.append(c);
    });
    tray.hidden = !tray.childElementCount;
  }

  function firstSentence(t) {
    const s = (t || '').replace(/[#*`_>]/g, '').trim();
    const m = s.match(/^(.{20,160}?[.!?])(\s|$)/);
    return m ? m[1] : s.length > 160 ? s.slice(0, 159) + '…' : s;
  }
})();
