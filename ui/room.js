// The back office in clay: the assistant at the front desk, agents at desks, a bench for the
// queue, the phase board, and the machine rack. Driven by setAgents / setLead / setStatus.
(function () {
  'use strict';
  const P = {
    bg: '#f0dfe0', sky: '#fff3ef', ground: '#d9b8b8', floor: '#ecd8d1', wall: '#f3d9d2', wall2: '#e9c8c0',
    wood: '#e3b58f', leg: '#c99b8d', counter: '#b48ab6', counterTop: '#fbeee9', laptop: '#7a6a80', screenOff: '#a396a8',
    accent: '#ef8354', ok: '#3fae7a', bad: '#e0605e', wait: '#a08f99', bench: '#c7a3b9', plant: '#6cbf8f', pot: '#e6a07c',
    board: '#5b4a63', boardFg: '#fff3ef', boardDim: '#8e7a95', door: '#c99b8d', eye: '#3b2a33', dark: '#4a3a46',
    gold: '#f2c14e', white: '#fffaf7', rack: '#6e5c76', hat: '#ffd56b',
  };
  Object.assign(P, ((window.BMA_PALETTES || {})[window.BMA_PALETTE] || {}).room);  // palettes.js
  const DESKS = [{ x: -2.4, z: -0.6 }, { x: 0.2, z: -0.6 }, { x: 2.8, z: -0.6 }, { x: -2.4, z: -2.8 }, { x: 0.2, z: -2.8 }, { x: 2.8, z: -2.8 }];
  const OVERFLOW = [{ x: -2.6, z: 1.0 }, { x: -1.8, z: 1.3 }, { x: 3.2, z: 1.0 }, { x: 3.9, z: 1.4 }, { x: -3.2, z: 1.5 }, { x: 4.4, z: 0.8 }];
  const SEATS = [1.3, 2.2, 3.1];
  const QUEUE_OVERFLOW = [{ x: -4.6, z: 3.6 }, { x: -4.1, z: 3.9 }, { x: -3.6, z: 3.6 }];
  const DOOR = { x: -5.4, z: -0.5, y: 0 };
  const FRONT = { x: 0.6, z: 2.0 };
  const AISLE_X = -4.4;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const now = () => performance.now() / 1000;

  let THREE, renderer, scene, camera, stage, canvas, layer, avatarRoot, refs = {};
  const figs = new Map();       // agent id → figure
  const deskUse = new Map();    // slot key → agent id
  let lead = { text: 'Hi! I\'ll show who is working on what.', at: 0, fig: null, bubble: null };
  const orbit = { theta: 0.62, phi: 0.6, r: 17, target: null };
  let status = null, heavyRunning = 0;

  // ---------- geometry helpers ----------
  function geo(kind, d) {
    switch (kind) {
      case 'box': return new THREE.BoxGeometry(d[0], d[1], d[2]);
      case 'sph': return new THREE.SphereGeometry(d[0], 32, 20);
      case 'cyl': return new THREE.CylinderGeometry(d[0], d[1], d[2], d[3] || 28);
      case 'cap': return new THREE.CapsuleGeometry(d[0], d[1], 8, 28);
      case 'cone': return new THREE.ConeGeometry(d[0], d[1], 28);
      case 'tor': return new THREE.TorusGeometry(d[0], d[1], 12, 40, d[2] || Math.PI * 2);
      case 'hemi': return new THREE.SphereGeometry(d[0], 32, 12, 0, Math.PI * 2, 0, Math.PI / 2);
    }
  }
  function part(kind, d, color, o = {}) {
    const mat = o.basic ? new THREE.MeshBasicMaterial({ color }) : new THREE.MeshStandardMaterial({ color, roughness: 0.92, metalness: 0 });
    const m = new THREE.Mesh(geo(kind, d), mat);
    m.castShadow = !o.noCast; m.receiveShadow = true;
    return m;
  }
  const at = (m, x, y, z, rx = 0, ry = 0, rz = 0) => { m.position.set(x, y, z); m.rotation.set(rx, ry, rz); return m; };
  const lighten = (hex, k) => '#' + new THREE.Color(hex).lerp(new THREE.Color('#ffffff'), k).getHexString();
  function dispose(obj) {
    obj.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) { if (o.material.map) o.material.map.dispose(); o.material.dispose(); }
    });
  }
  function canvasTex(w, h, draw) {
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    draw(c.getContext('2d'));
    return new THREE.CanvasTexture(c);
  }

  // ---------- room ----------
  function drawBoard(x) {
    const st = status;
    x.fillStyle = P.board; x.fillRect(0, 0, 640, 300);
    x.fillStyle = P.boardFg; x.textAlign = 'left';
    const cur = st && st.phases && st.phases.find((p) => p.id === st.current);
    const title = cur ? `Phase ${cur.title}` : st && st.next && st.next.length ? 'Next: ' + st.next.join(', ') : 'build-my-app';
    x.font = '600 34px ui-sans-serif, -apple-system, sans-serif'; x.fillText(title.slice(0, 30), 36, 62);
    x.globalAlpha = 0.7; x.font = '18px ui-monospace, Menlo, monospace';
    x.fillText(st ? `${st.project || ''} · ${st.autonomy || ''} autonomy` : '', 36, 96); x.globalAlpha = 1;
    const phases = (st && st.phases) || [];
    for (let i = 0; i < 9; i++) {
      const ph = phases[i] || {}, cx = 52 + i * 67, cy = 168;
      const done = ph.status === 'done', active = ph.status === 'in_progress' || ph.status === 'gate';
      if (i < 8) { x.strokeStyle = done ? P.ok : P.boardDim; x.lineWidth = 4; x.beginPath(); x.moveTo(cx + 15, cy); x.lineTo(cx + 52, cy); x.stroke(); }
      x.beginPath(); x.arc(cx, cy, 15, 0, Math.PI * 2);
      if (done) { x.fillStyle = P.ok; x.fill(); }
      else if (active) { x.fillStyle = P.accent; x.fill(); x.strokeStyle = P.boardFg; x.lineWidth = 3; x.stroke(); }
      else { x.strokeStyle = P.boardDim; x.lineWidth = 3; x.stroke(); }
      x.fillStyle = P.boardFg; x.font = '500 16px ui-monospace, Menlo, monospace'; x.textAlign = 'center';
      x.fillText(String(i), cx, cy + 42); x.textAlign = 'left';
    }
    const nd = st && st.decisions ? st.decisions.length : 0, nl = st && st.loops ? st.loops.length : 0;
    x.font = '500 21px ui-monospace, Menlo, monospace';
    x.fillText(`${nd} decision${nd === 1 ? '' : 's'} open   ${nl} review loop${nl === 1 ? '' : 's'}`, 36, 266);
  }
  function refreshBoard() {
    if (!refs.board) return;
    const old = refs.board.material.map;
    refs.board.material.map = canvasTex(640, 300, drawBoard);
    refs.board.material.needsUpdate = true;
    if (old) old.dispose();
  }

  // ---------- preview TV (left wall): the app as it looks now; click to open ----------
  let preview = null, previewImg = null, previewImgUrl = null;
  function drawTv(x) {
    const w = x.canvas.width, h = x.canvas.height;
    x.fillStyle = P.board; x.fillRect(0, 0, w, h);
    if (preview && previewImg && previewImg.complete && previewImg.naturalWidth) {
      const s = Math.min(w / previewImg.naturalWidth, (h - 44) / previewImg.naturalHeight);
      const iw = previewImg.naturalWidth * s, ih = previewImg.naturalHeight * s;
      x.drawImage(previewImg, (w - iw) / 2, (h - 44 - ih) / 2, iw, ih);
    } else {
      x.fillStyle = P.boardDim; x.font = '600 64px ui-sans-serif, -apple-system, sans-serif';
      x.textAlign = 'center'; x.textBaseline = 'middle';
      x.fillText(preview ? '▶' : '·', w / 2, (h - 44) / 2);
    }
    x.fillStyle = 'rgba(0,0,0,.35)'; x.fillRect(0, h - 44, w, 44);
    x.fillStyle = P.boardFg; x.font = '600 22px ui-sans-serif, -apple-system, sans-serif';
    x.textAlign = 'left'; x.textBaseline = 'middle';
    const line = !preview ? 'No preview yet' : preview.live ? `${preview.label} · click to open` : `${preview.label} · stopped`;
    x.fillText(line.length > 40 ? line.slice(0, 39) + '…' : line, 16, h - 22);
    if (preview && preview.live) { x.fillStyle = P.ok; x.beginPath(); x.arc(w - 22, h - 22, 8, 0, Math.PI * 2); x.fill(); }
  }
  function refreshTv() {
    if (!refs.tv) return;
    const old = refs.tv.material.map;
    refs.tv.material.map = canvasTex(480, 300, drawTv);
    refs.tv.material.needsUpdate = true;
    if (old) old.dispose();
  }
  function setPreview(p) {
    preview = p;
    const url = p && p.img;
    if (url !== previewImgUrl) {
      previewImgUrl = url;
      previewImg = null;
      if (url) { previewImg = new Image(); previewImg.onload = refreshTv; previewImg.src = url; }
    }
    refreshTv();
  }

  function buildRoom() {
    const g = new THREE.Group(); const add = (m) => (g.add(m), m);
    add(at(part('box', [12.2, 0.2, 9.2], P.floor, { noCast: true }), 0, -0.1, 0));
    add(at(part('box', [12.2, 3, 0.2], P.wall), 0, 1.5, -4.6));
    add(at(part('box', [0.2, 3, 9.2], P.wall2), -6.1, 1.5, 0));
    add(at(part('box', [0.06, 2.0, 1.0], P.door), -5.97, 1.0, DOOR.z));
    add(at(part('box', [0.1, 0.12, 1.24], P.leg), -5.97, 2.06, DOOR.z));
    add(at(part('sph', [0.05], P.gold), -5.92, 1.0, DOOR.z + 0.36));
    add(at(part('box', [0.9, 0.02, 1.1], P.counter, { noCast: true }), -5.45, 0.01, DOOR.z));
    add(at(part('box', [3.5, 1.75, 0.06], P.leg), 1.2, 2.05, -4.48));
    refs.board = add(at(new THREE.Mesh(new THREE.PlaneGeometry(3.3, 1.55), new THREE.MeshBasicMaterial({ map: canvasTex(640, 300, drawBoard) })), 1.2, 2.05, -4.44));
    refs.panels = [];
    DESKS.forEach((d) => {
      add(at(part('box', [1.5, 0.06, 0.8], P.wood), d.x, 0.65, d.z));
      add(at(part('box', [0.06, 0.62, 0.66], P.leg), d.x - 0.66, 0.31, d.z));
      add(at(part('box', [0.06, 0.62, 0.66], P.leg), d.x + 0.66, 0.31, d.z));
      add(at(part('box', [0.58, 0.03, 0.38], P.laptop), d.x, 0.695, d.z - 0.02));
      const lid = new THREE.Group(); lid.position.set(d.x, 0.71, d.z + 0.17); lid.rotation.x = 0.18; g.add(lid);
      lid.add(at(part('box', [0.58, 0.34, 0.025], P.laptop), 0, 0.17, 0));
      const panel = at(part('box', [0.16, 0.16, 0.01], P.screenOff, { basic: true, noCast: true }), 0, 0.19, 0.016);
      lid.add(panel); refs.panels.push(panel);
    });
    add(at(part('box', [3.0, 0.8, 0.6], P.counter), FRONT.x, 0.4, 2.62));
    add(at(part('box', [3.2, 0.06, 0.76], P.counterTop), FRONT.x, 0.83, 2.62));
    add(at(part('hemi', [0.09], P.gold), FRONT.x + 1.15, 0.86, 2.6));
    add(at(part('cyl', [0.1, 0.1, 0.02], P.dark), FRONT.x + 1.15, 0.87, 2.6));
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.26), new THREE.MeshBasicMaterial({
      map: canvasTex(440, 104, (x) => {
        x.fillStyle = P.board; x.fillRect(0, 0, 440, 104);
        x.fillStyle = P.boardFg; x.font = '600 46px ui-sans-serif, -apple-system, sans-serif';
        x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('Ask me', 220, 54);
      }) }));
    add(at(sign, FRONT.x - 0.55, 0.4, 2.925));
    add(at(part('box', [0.55, 0.1, 2.7], P.bench), -5.25, 0.37, 2.2));
    add(at(part('box', [0.5, 0.32, 0.08], P.leg), -5.25, 0.16, 1.0));
    add(at(part('box', [0.5, 0.32, 0.08], P.leg), -5.25, 0.16, 3.4));
    add(at(part('box', [0.06, 1.04, 1.64], P.dark), -5.97, 1.85, 2.2));
    refs.tv = add(at(new THREE.Mesh(new THREE.PlaneGeometry(1.52, 0.95), new THREE.MeshBasicMaterial({ map: canvasTex(480, 300, drawTv) })), -5.9, 1.85, 2.2));
    refs.tv.rotation.y = Math.PI / 2;
    add(at(part('box', [0.75, 1.9, 0.6], P.rack), 5.2, 0.95, -3.95));
    refs.rack = [1.55, 1.25, 0.95].map((y) => add(at(part('box', [0.46, 0.08, 0.02], P.screenOff, { basic: true, noCast: true }), 5.2, y, -3.64)));
    [[-5.4, -3.9], [5.2, 3.7], [-1.0, 2.7]].forEach(([x, z], i) => {
      const s = i === 2 ? 0.45 : 1, y0 = i === 2 ? 0.86 : 0;
      add(at(part('cyl', [0.22 * s, 0.17 * s, 0.4 * s], P.pot), x, y0 + 0.2 * s, z));
      add(at(part('cone', [0.34 * s, 0.9 * s], P.plant), x, y0 + 0.85 * s, z));
    });
    return g;
  }

  // ---------- avatars ----------
  function addProp(g, prop, col, spin) {
    const add = (m, parent = g) => (parent.add(m), m);
    switch (prop) {
      case 'headset':
        add(at(part('tor', [0.24, 0.028, Math.PI], P.dark), 0, 1.08, 0));
        add(at(part('cyl', [0.065, 0.065, 0.07], P.dark), -0.24, 1.08, 0, 0, 0, Math.PI / 2));
        add(at(part('cyl', [0.065, 0.065, 0.07], P.dark), 0.24, 1.08, 0, 0, 0, Math.PI / 2));
        add(at(part('box', [0.028, 0.028, 0.2], P.dark), -0.2, 0.98, 0.1, 0, 0.6, 0));
        add(at(part('box', [0.12, 0.07, 0.04], P.gold), 0, 0.68, 0.235));
        break;
      case 'hardhat':
        add(at(part('hemi', [0.25], P.hat), 0, 1.1, 0));
        add(at(part('cyl', [0.31, 0.31, 0.03], P.hat), 0, 1.11, 0));
        add(at(part('box', [0.05, 0.05, 0.44], lighten(P.hat, 0.4)), 0, 1.33, 0));
        break;
      case 'glasses':
        add(at(part('tor', [0.065, 0.016], P.dark), -0.085, 1.1, 0.214));
        add(at(part('tor', [0.065, 0.016], P.dark), 0.085, 1.1, 0.214));
        add(at(part('box', [0.05, 0.014, 0.014], P.dark), 0, 1.11, 0.22));
        break;
      case 'clipboard': case 'book': {
        const cb = new THREE.Group(); cb.position.set(0.3, 0.56, 0.18); cb.rotation.set(-0.35, -0.45, 0.12); g.add(cb);
        if (prop === 'clipboard') {
          add(part('box', [0.22, 0.3, 0.025], P.wood), cb);
          add(at(part('box', [0.18, 0.22, 0.01], P.white), 0, -0.01, 0.018), cb);
          add(at(part('box', [0.09, 0.035, 0.03], P.dark), 0, 0.15, 0.015), cb);
        } else {
          add(part('box', [0.24, 0.3, 0.07], '#8a5a44'), cb);
          add(at(part('box', [0.22, 0.28, 0.05], P.white), 0.012, 0, 0), cb);
        }
        break; }
      case 'beanie':
        add(at(part('hemi', [0.238], P.white), 0, 1.12, 0));
        add(at(part('cyl', [0.245, 0.245, 0.07], lighten(col, 0.1)), 0, 1.13, 0));
        add(at(part('sph', [0.068], col), 0, 1.38, 0));
        break;
      case 'cap':
        add(at(part('hemi', [0.235], P.white), 0, 1.12, 0));
        add(at(part('box', [0.26, 0.025, 0.2], col), 0, 1.13, 0.25));
        break;
      case 'shield':
        add(at(part('box', [0.38, 0.085, 0.12], P.dark), 0, 1.11, 0.17));
        add(at(part('cyl', [0.09, 0.09, 0.025], P.gold), 0, 0.62, 0.24, Math.PI / 2, 0, 0));
        break;
      case 'scarf':
        add(at(part('tor', [0.2, 0.055], P.accent), 0, 0.86, 0, Math.PI / 2, 0, 0));
        add(at(part('box', [0.08, 0.24, 0.05], P.accent), 0.11, 0.7, 0.2, 0, 0, 0.15));
        break;
      case 'antenna':
        add(at(part('cyl', [0.012, 0.012, 0.26], P.dark), 0, 1.42, 0));
        add(at(part('sph', [0.05], P.gold), 0, 1.57, 0));
        break;
      case 'beret':
        add(at(part('cyl', [0.25, 0.24, 0.07], P.dark), 0.03, 1.27, 0, 0, 0, -0.22));
        add(at(part('sph', [0.03], P.dark), 0.05, 1.32, 0));
        break;
      case 'bow':
        add(at(part('cone', [0.07, 0.13], P.accent), -0.08, 1.31, 0, 0, 0, -Math.PI / 2));
        add(at(part('cone', [0.07, 0.13], P.accent), 0.08, 1.31, 0, 0, 0, Math.PI / 2));
        add(at(part('sph', [0.035], P.accent), 0, 1.31, 0));
        break;
      case 'tophat':
        add(at(part('cyl', [0.26, 0.26, 0.025], P.dark), 0, 1.28, 0));
        add(at(part('cyl', [0.17, 0.17, 0.26], P.dark), 0, 1.41, 0));
        add(at(part('cyl', [0.172, 0.172, 0.05], P.gold), 0, 1.32, 0));
        break;
      case 'propeller': {
        add(at(part('hemi', [0.235], lighten(col, 0.3)), 0, 1.12, 0));
        add(at(part('cyl', [0.012, 0.012, 0.08], P.dark), 0, 1.39, 0));
        const blades = add(at(part('box', [0.34, 0.012, 0.05], P.accent), 0, 1.43, 0));
        spin.push(blades);
        break; }
      case 'headband':
        add(at(part('tor', [0.226, 0.032], P.accent), 0, 1.16, 0, Math.PI / 2, 0, 0));
        break;
      case 'halo':
        add(at(part('tor', [0.15, 0.022], P.gold, { basic: true, noCast: true }), 0, 1.46, 0, Math.PI / 2, 0, 0));
        break;
      case 'flag':
        add(at(part('cyl', [0.012, 0.012, 0.62], P.dark), 0.3, 0.78, 0.05));
        add(at(part('box', [0.2, 0.13, 0.01], P.accent), 0.4, 1.02, 0.05));
        break;
    }
  }

  function buildAvatar(type) {
    const c = window.bmaCast(type);
    const g = new THREE.Group(); const add = (m, parent = g) => (parent.add(m), m);
    const col = c.color, spin = [];
    add(at(part('cap', [0.24, 0.4], col), 0, 0.44, 0));
    add(at(part('sph', [0.22], lighten(col, 0.3)), 0, 1.08, 0));
    if (c.prop !== 'shield') {
      add(at(part('sph', [0.034], P.eye, { noCast: true }), -0.08, 1.1, 0.198));
      add(at(part('sph', [0.034], P.eye, { noCast: true }), 0.08, 1.1, 0.198));
    }
    addProp(g, c.prop, col, spin);
    const ind = new THREE.Group(); ind.position.y = 1.66; g.add(ind);
    const mk = () => { const s = new THREE.Group(); ind.add(s); s.visible = false; return s; };
    const I = { working: mk(), queued: mk(), done: mk(), stuck: mk() };
    add(part('tor', [0.11, 0.03], P.accent, { noCast: true }), I.working);
    add(at(part('cone', [0.085, 0.12], P.wait, { noCast: true }), 0, 0.06, 0, Math.PI, 0, 0), I.queued);
    add(at(part('cone', [0.085, 0.12], P.wait, { noCast: true }), 0, -0.06, 0), I.queued);
    add(at(part('box', [0.06, 0.14, 0.06], P.ok, { noCast: true }), -0.06, -0.02, 0, 0, 0, 0.8), I.done);
    add(at(part('box', [0.06, 0.28, 0.06], P.ok, { noCast: true }), 0.055, 0.04, 0, 0, 0, -0.6), I.done);
    add(at(part('cyl', [0.038, 0.026, 0.18], P.bad, { noCast: true }), 0, 0.05, 0), I.stuck);
    add(at(part('sph', [0.038], P.bad, { noCast: true }), 0, -0.09, 0), I.stuck);
    return { g, I, ind, spin };
  }

  // ---------- places ----------
  function claim(kind, id) {
    const list = kind === 'desk' ? DESKS.map((_, i) => 'd' + i).concat(OVERFLOW.map((_, i) => 'o' + i))
      : SEATS.map((_, i) => 's' + i).concat(QUEUE_OVERFLOW.map((_, i) => 'q' + i));
    for (const key of list) if (!deskUse.has(key) || deskUse.get(key) === id) { deskUse.set(key, id); return key; }
    return list[list.length - 1];
  }
  function release(id, keep) {
    for (const [k, v] of deskUse) if (v === id && k !== keep) deskUse.delete(k);
  }
  function spotOf(key) {
    const n = +key.slice(1);
    if (key[0] === 'd') return { x: DESKS[n].x, z: DESKS[n].z - 0.62, y: 0, rot: 0 };
    if (key[0] === 'o') return { x: OVERFLOW[n].x, z: OVERFLOW[n].z, y: 0, rot: 0 };
    if (key[0] === 's') return { x: -5.22, z: SEATS[n], y: 0.42, rot: Math.PI / 2 };
    return { x: QUEUE_OVERFLOW[n].x, z: QUEUE_OVERFLOW[n].z, y: 0, rot: Math.PI / 2 };
  }
  function makePath(from, to) {
    if (Math.hypot(from.x - to.x, from.z - to.z) < 0.05 && Math.abs(from.y - to.y) < 0.01) return [];
    return [{ x: AISLE_X, z: from.z, y: 0 }, { x: AISLE_X, z: to.z, y: 0 }, to];
  }
  function goTo(f, key) {
    if (f.place === key) return;
    f.place = key;
    release(f.id, key);
    f.rest = spotOf(key).rot;
    f.path = makePath(f.pos, spotOf(key));
  }

  // ---------- public: data in ----------
  function setAgents(list, initial) {
    if (!scene) return;
    const t = now(), seen = new Set();
    list.forEach((a) => {
      seen.add(a.id);
      let f = figs.get(a.id);
      if (!f) {
        if (a.status === 'done') return;   // finished already: it shows in the roster, not the room
        const av = buildAvatar(a.type);
        f = { id: a.id, a, ...av, pos: { ...DOOR }, path: [], rot: 0, rest: 0, place: null, pop: initial ? 1 : 0,
          saidAt: initial ? -99 : t, pinned: false, phase: Math.random() * 6, doneAt: null, leaving: false };
        av.g.userData.aid = a.id;
        avatarRoot.add(av.g);
        figs.set(a.id, f);
        const key = claim(a.status === 'queued' ? 'seat' : 'desk', a.id);
        if (initial) { Object.assign(f.pos, spotOf(key)); f.place = key; f.rest = f.rot = spotOf(key).rot; }
        else goTo(f, key);
      }
      if (f.leaving) return;
      if (f.a.status !== a.status || f.a.now !== a.now) f.saidAt = t;
      if (a.status === 'done' && f.a.status !== 'done') f.doneAt = t;
      f.a = a;
      const want = a.status === 'queued' ? 'seat' : 'desk';
      if (f.place && (want === 'seat') !== /^[sq]/.test(f.place)) goTo(f, claim(want, a.id));
    });
    figs.forEach((f) => { if (!seen.has(f.id)) leave(f); });
  }
  function leave(f) {
    if (f.leaving) return;
    f.leaving = true; release(f.id); f.place = 'door';
    f.path = makePath(f.pos, DOOR);
  }
  function setLead(text) { if (text && text !== lead.text) { lead.text = text; lead.at = now(); } }
  function setStatus(st) { status = st; refreshBoard(); }
  function setHeavy(n) { heavyRunning = n || 0; }

  // ---------- overlay ----------
  const stateColor = (s) => ({ working: P.accent, queued: P.wait, done: P.ok, stuck: P.bad }[s] || P.wait);
  function bubbleFor(f, name, isLead) {
    const b = document.createElement('div'); b.className = 'bubble' + (isLead ? ' lead' : '');
    b.innerHTML = '<div class="who"><span class="dot"></span><span class="nm"></span></div><div class="say"></div>';
    b.querySelector('.nm').textContent = name;
    layer.appendChild(b);
    return b;
  }
  const v3 = () => new THREE.Vector3();
  let tmp;
  function project(x, y, z) {
    tmp.set(x, y, z).project(camera);
    return { x: (tmp.x + 1) / 2 * stage.clientWidth, y: (1 - tmp.y) / 2 * stage.clientHeight, behind: tmp.z > 1 };
  }
  function place(b, p) { b.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -100%)`; }

  // ---------- camera ----------
  function fit() {
    const w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    placeCamera();
  }
  function placeCamera() {
    const stretch = Math.max(1, 1.55 / camera.aspect), r = orbit.r * stretch, t = orbit.target;
    camera.position.set(t.x + r * Math.cos(orbit.phi) * Math.sin(orbit.theta), t.y + r * Math.sin(orbit.phi), t.z + r * Math.cos(orbit.phi) * Math.cos(orbit.theta));
    camera.lookAt(t);
  }

  // ---------- frame ----------
  let last = now(), lastDraw = 0;
  function lerpAngle(a, b, k) { let d = ((b - a + Math.PI) % (Math.PI * 2)) - Math.PI; if (d < -Math.PI) d += Math.PI * 2; return a + d * k; }
  function frame() {
    requestAnimationFrame(frame);
    const t = now(), dt = Math.min(0.05, t - last); last = t;
    let moving = false;
    const anim = reduced ? 0 : t;
    const open = [...figs.values()].filter((f) => !f.leaving && t - f.saidAt < 5).sort((p, q) => q.saidAt - p.saidAt).slice(0, 2);
    const deskState = new Array(DESKS.length).fill(null);

    figs.forEach((f) => {
      if (f.pop < 1) { f.pop = Math.min(1, f.pop + dt * 2.5); moving = true; }
      if (f.doneAt && !f.leaving && t - f.doneAt > 6) leave(f);
      if (f.path.length) {
        moving = true;
        const wp = f.path[0], dx = wp.x - f.pos.x, dz = wp.z - f.pos.z, dist = Math.hypot(dx, dz), sp = 1.7 * dt;
        if (dist <= sp) { f.pos.x = wp.x; f.pos.z = wp.z; f.path.shift(); }
        else { f.pos.x += dx / dist * sp; f.pos.z += dz / dist * sp; f.rot = lerpAngle(f.rot, Math.atan2(dx, dz), 0.2); }
        f.pos.y += (wp.y - f.pos.y) * Math.min(1, dt * 6);
        if (!f.path.length && f.leaving) { f.gone = true; return; }
      } else {
        f.rot = lerpAngle(f.rot, f.rest, 0.12);
      }
      const walking = f.path.length > 0, s = f.a.status;
      let bob = 0, sway = 0;
      if (walking) bob = Math.abs(Math.sin(anim * 11 + f.phase)) * 0.06;
      else if (s === 'working') bob = Math.sin(anim * 3 + f.phase) * 0.012;
      else if (s === 'stuck') sway = Math.sin(anim * 18) * 0.06;
      f.g.position.set(f.pos.x, f.pos.y + bob, f.pos.z);
      f.g.rotation.y = f.rot + sway;
      f.g.scale.setScalar(Math.max(0.01, reduced ? 1 : 1 - Math.pow(1 - f.pop, 3)));
      Object.entries(f.I).forEach(([k, grp]) => (grp.visible = !walking && !f.leaving && k === s));
      f.I.working.rotation.set(0.5, anim * 2.5, 0);
      f.ind.position.y = 1.66 + Math.sin(anim * 2 + f.phase) * 0.03;
      f.ind.rotation.y = -f.rot - sway + orbit.theta;
      f.spin.forEach((m) => (m.rotation.y = anim * 9));
      if (f.place && f.place[0] === 'd' && !walking) deskState[+f.place.slice(1)] = s;

      // bubble
      if (!f.bubble) f.bubble = bubbleFor(f, f.a.type);
      const pr = project(f.pos.x, f.pos.y + 1.95, f.pos.z);
      f.bubble.style.opacity = pr.behind || f.leaving ? 0 : 1;
      place(f.bubble, pr);
      const isOpen = f.pinned || open.includes(f);
      f.bubble.classList.toggle('open', isOpen);
      f.bubble.style.zIndex = isOpen ? 3 : 1;
      f.bubble.querySelector('.dot').style.background = walking ? P.wait : stateColor(s);
      const say = (s === 'done' && f.a.result) || f.a.now || f.a.desc || '';
      const el = f.bubble.querySelector('.say'); if (el.textContent !== say) el.textContent = say;
    });
    figs.forEach((f, id) => {
      if (!f.gone) return;
      avatarRoot.remove(f.g); dispose(f.g); if (f.bubble) f.bubble.remove(); figs.delete(id);
    });
    refs.panels.forEach((m, i) => {
      const s = deskState[i];
      m.material.color.set(!s ? P.screenOff : s === 'stuck' ? ((Math.floor(t * 3) % 2) ? P.bad : P.screenOff) : s === 'done' ? P.ok : s === 'queued' ? P.screenOff : P.accent);
    });
    refs.rack.forEach((m, i) => m.material.color.set(i < heavyRunning ? P.ok : P.screenOff));

    // assistant at the front desk
    const hop = Math.max(0, 1 - (t - lead.at) * 3) * 0.08;
    lead.fig.g.position.set(FRONT.x, Math.abs(Math.sin(anim * 1.6)) * 0.015 + hop, FRONT.z);
    lead.fig.g.rotation.y = Math.sin(anim * 0.7) * 0.15;
    const lp = project(FRONT.x, 2.05, FRONT.z);
    place(lead.bubble, lp);
    const ls = lead.bubble.querySelector('.say'); if (ls.textContent !== lead.text) ls.textContent = lead.text;
    if (hop > 0) moving = true;

    // Draw at 30 fps while something moves, 12 fps otherwise (spinning rings, blinking).
    const fps = moving || dragging ? 30 : 12;
    if (t - lastDraw < 1 / fps - 0.004) return;
    lastDraw = t;
    renderer.render(scene, camera);
  }

  // ---------- input ----------
  let down = null, dragging = false;
  function bindInput() {
    canvas.addEventListener('pointerdown', (e) => { down = { x: e.clientX, theta: orbit.theta, moved: false }; });
    window.addEventListener('pointermove', (e) => {
      if (!down) return;
      const dx = e.clientX - down.x;
      if (Math.abs(dx) > 4) down.moved = dragging = true;
      if (!down.moved) return;
      orbit.theta = Math.min(1.45, Math.max(-0.35, down.theta - dx * 0.006));
      placeCamera();
    });
    window.addEventListener('pointerup', (e) => { if (down && !down.moved) pick(e); down = null; dragging = false; });
  }
  function pick(e) {
    const r = canvas.getBoundingClientRect(), ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    if (refs.tv && preview && preview.live && ray.intersectObject(refs.tv).length) {
      if (window.BmaRoom.onPreview) window.BmaRoom.onPreview(preview);
      return;
    }
    const hit = ray.intersectObjects(avatarRoot.children, true)[0];
    let o = hit && hit.object; while (o && !o.userData.aid) o = o.parent;
    const f = o && figs.get(o.userData.aid);
    if (f) f.pinned = !f.pinned;
  }

  // ---------- init ----------
  function init(stageEl, canvasEl, layerEl) {
    THREE = window.THREE;
    if (!THREE) return false;
    stage = stageEl; canvas = canvasEl; layer = layerEl;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    } catch (e) { return false; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    tmp = v3();
    orbit.target = new THREE.Vector3(0.1, 0.6, 0);
    scene = new THREE.Scene();
    scene.background = new THREE.Color(P.bg);
    scene.fog = new THREE.Fog(P.bg, 18, 34);
    scene.add(new THREE.AmbientLight(0xffffff, 0.38));
    scene.add(new THREE.HemisphereLight(P.sky, P.ground, 0.5));
    const d = new THREE.DirectionalLight(0xffffff, 0.6);
    d.position.set(4, 9, 5); d.castShadow = true; d.shadow.mapSize.set(1024, 1024); d.shadow.radius = 6; d.shadow.bias = -0.0008;
    Object.assign(d.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 34 });
    scene.add(d);
    scene.add(buildRoom());
    avatarRoot = new THREE.Group(); scene.add(avatarRoot);
    lead.fig = buildAvatar('assistant');
    lead.fig.g.scale.setScalar(1.2);
    scene.add(lead.fig.g);
    lead.bubble = bubbleFor(null, 'Assistant', true);
    lead.bubble.querySelector('.dot').style.background = window.bmaCast('assistant').color;
    camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
    new ResizeObserver(fit).observe(stage);
    fit();
    bindInput();
    requestAnimationFrame(frame);
    return true;
  }

  window.BmaRoom = { init, setAgents, setLead, setStatus, setHeavy, setPreview, onPreview: null };
})();
