// Live view: one server-sent event stream feeds the status panel, the front-desk feed,
// the roster, and the 3D room.
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const token = new URLSearchParams(location.search).get('token');
  const has3d = window.BmaRoom && window.BmaRoom.init($('#stage'), $('#scene'), $('#layer'));
  if (!has3d) { $('#no3d').hidden = false; $('#scene').hidden = true; }
  const room = has3d ? window.BmaRoom : { setAgents() {}, setLead() {}, setStatus() {}, setHeavy() {} };

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
    gotSnapshot = true;
    if (!(d.feed || []).length) emptyFeed();
  });
  es.addEventListener('state', (m) => renderState(JSON.parse(m.data)));
  es.addEventListener('agents', (m) => renderAgents(JSON.parse(m.data), false));
  es.addEventListener('feed', (m) => addFeed(JSON.parse(m.data)));

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
    $('#feed').append(el('li', 'empty', 'Nothing yet. Talk to Claude in the terminal: your messages, its replies, and agent updates show up here.'));
  }
  function hhmm(ts) { return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  function addFeed(item) {
    const key = `${item.ts}|${item.who}|${item.text}`;
    if (seen.has(key)) return;
    seen.add(key);
    const feed = $('#feed');
    const empty = feed.querySelector('.empty'); if (empty) empty.remove();
    const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 60;
    const kind = item.who === 'you' ? 'you' : item.who === 'assistant' ? 'assistant' : 'agent';
    const li = el('li', kind);
    const who = el('div', 'who');
    who.append(el('b', null, item.who === 'you' ? 'You' : item.who === 'assistant' ? 'Assistant' : item.who));
    if (item.via) who.append(el('span', 'badge', item.via === 'terminal' ? '⌨ terminal' : '🌐 web'));
    who.append(el('span', null, hhmm(item.ts)));
    li.append(who, el('div', 'msg', item.text));
    feed.append(li);
    while (feed.children.length > 200) feed.firstChild.remove();
    if (nearBottom) feed.scrollTop = feed.scrollHeight;
    if (item.who === 'assistant') room.setLead(firstSentence(item.text));
  }
  function firstSentence(t) {
    const s = (t || '').replace(/[#*`_>]/g, '').trim();
    const m = s.match(/^(.{20,160}?[.!?])(\s|$)/);
    return m ? m[1] : s.length > 160 ? s.slice(0, 159) + '…' : s;
  }
})();
