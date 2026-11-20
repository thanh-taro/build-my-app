// Color palettes for the page and the clay room. Loaded in <head> so the page paints in the chosen
// colors. The choice is kept per browser (localStorage) and can be forced with ?palette=<name>.
(function () {
  'use strict';
  const PALETTES = {
    mint: {
      label: 'Mint',
      room: {
        bg: '#dcebe6', sky: '#f2faf7', ground: '#b8d3cb', floor: '#e6f0ec', wall: '#d4e8e1', wall2: '#c2ddd4',
        wood: '#e9d9b8', leg: '#b9c7b8', counter: '#6fa8a0', counterTop: '#f5faf8', laptop: '#5f6f78', screenOff: '#93a3aa',
        accent: '#3fa796', wait: '#94a6a2', bench: '#9fc7bd', pot: '#c9b48f', board: '#35524f', boardFg: '#effaf6',
        boardDim: '#7fa39c', door: '#a9bfb7', eye: '#25343a', dark: '#33464a', white: '#fbfefd', rack: '#4f6670',
      },
      ui: {
        light: { bg: '#eef3f2', surface: '#ffffff', ink: '#1f2b2b', muted: '#5a6b6b', line: '#d8e3e1', chip: '#e7efed',
                 accent: '#277a6f', 'on-accent': '#ffffff', you: '#e6f0fa' },
        dark: { bg: '#141a1a', surface: '#1b2323', ink: '#e6f0ee', muted: '#9db1ae', line: '#2c3838', chip: '#253030',
                accent: '#5cc8b6', 'on-accent': '#0d1b19', you: '#1f2c3a' },
        room: '#dcebe6', bubble: '#f6fbfa', 'bubble-ink': '#24363a',
      },
    },
    sky: {
      label: 'Sky',
      room: {
        bg: '#dde6f2', sky: '#f3f7fc', ground: '#b9c8dc', floor: '#e8eef6', wall: '#d8e3f1', wall2: '#c6d5ea',
        wood: '#e8dcc6', leg: '#aebccf', counter: '#7b93c9', counterTop: '#f7f9fd', laptop: '#5d6678', screenOff: '#98a2b5',
        accent: '#4f86d9', wait: '#97a3b6', bench: '#a9bde0', pot: '#c8b598', board: '#2f3e5c', boardFg: '#eef3fb',
        boardDim: '#7b8db0', door: '#aab8cc', eye: '#232a3a', dark: '#323b4f', white: '#fbfcfe', rack: '#4c5874',
      },
      ui: {
        light: { bg: '#eff2f7', surface: '#ffffff', ink: '#1e2533', muted: '#5a6579', line: '#d9dfea', chip: '#e8edf5',
                 accent: '#3866b8', 'on-accent': '#ffffff', you: '#e9eefb' },
        dark: { bg: '#12161e', surface: '#1a2029', ink: '#e5eaf3', muted: '#9aa6ba', line: '#2b3442', chip: '#232b38',
                accent: '#7aa7f0', 'on-accent': '#0e1626', you: '#22304a' },
        room: '#dde6f2', bubble: '#f7f9fd', 'bubble-ink': '#232b3c',
      },
    },
    slate: {
      label: 'Slate',
      room: {
        bg: '#e3e5ea', sky: '#f6f7f9', ground: '#c4c8d0', floor: '#eceef1', wall: '#e0e3e8', wall2: '#d0d4dc',
        wood: '#dcd6cc', leg: '#b3b8c2', counter: '#7e7fb8', counterTop: '#f8f8fa', laptop: '#5c606c', screenOff: '#9ca1ad',
        accent: '#6366c9', wait: '#9ea3ad', bench: '#b4b6cf', pot: '#bfb3a3', board: '#2e3140', boardFg: '#f1f2f6',
        boardDim: '#80859a', door: '#b3b8c2', eye: '#262833', dark: '#363948', white: '#fcfcfd', rack: '#50546a',
      },
      ui: {
        light: { bg: '#f1f2f4', surface: '#ffffff', ink: '#20222a', muted: '#5f6370', line: '#dee0e5', chip: '#eceef1',
                 accent: '#5457b8', 'on-accent': '#ffffff', you: '#eceefa' },
        dark: { bg: '#131418', surface: '#1b1c22', ink: '#e8e9ee', muted: '#a0a3ae', line: '#2d2f38', chip: '#25272f',
                accent: '#9a9cf2', 'on-accent': '#15162a', you: '#252a40' },
        room: '#e3e5ea', bubble: '#f8f8fa', 'bubble-ink': '#262833',
      },
    },
    clay: {
      label: 'Clay (warm)',
      room: {},  // the room's built-in colors
      ui: {
        light: { bg: '#f3eeee', surface: '#ffffff', ink: '#2e2229', muted: '#7a6a72', line: '#e6dadb', chip: '#f4e9e8',
                 accent: '#b14c6f', 'on-accent': '#ffffff', you: '#eef3fb' },
        dark: { bg: '#1b1619', surface: '#241d21', ink: '#f1e8ec', muted: '#b3a2aa', line: '#3a2f35', chip: '#30272c',
                accent: '#f08bb0', 'on-accent': '#2a1420', you: '#26303f' },
        room: '#f0dfe0', bubble: '#fff6f2', 'bubble-ink': '#4a3440',
      },
    },
  };
  const DEFAULT = 'mint';
  let saved = null;
  try { saved = localStorage.getItem('bma-palette'); } catch (e) { /* storage blocked: use the default */ }
  const asked = new URLSearchParams(location.search).get('palette');
  const name = PALETTES[asked] ? asked : PALETTES[saved] ? saved : DEFAULT;

  const dark = matchMedia('(prefers-color-scheme: dark)');
  function apply() {
    const ui = PALETTES[name].ui, root = document.documentElement.style;
    const vars = { ...(dark.matches ? ui.dark : ui.light), room: ui.room, bubble: ui.bubble, 'bubble-ink': ui['bubble-ink'] };
    for (const [k, v] of Object.entries(vars)) root.setProperty('--' + k, v);
  }
  apply();
  dark.addEventListener('change', apply);

  window.BMA_PALETTES = PALETTES;
  window.BMA_PALETTE = name;
  window.bmaSetPalette = (next) => {
    if (!PALETTES[next]) return;
    try { localStorage.setItem('bma-palette', next); } catch (e) { /* not remembered; still applied below */ }
    const u = new URL(location.href);
    u.searchParams.set('palette', next);  // also works when storage is blocked
    location.replace(u);  // the room builds its materials once, so reload to repaint it
  };
})();
