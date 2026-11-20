// Who's who in the room: one body color and one prop per agent type.
// Any agent type not listed (a new plugin agent, Explore, Plan, general-purpose...) still
// appears, with the neutral look and its type as its name.
window.BMA_CAST = {
  assistant:            { color: '#f2b84b', prop: 'headset',   role: 'Front desk' },
  'product-strategist': { color: '#e9a15b', prop: 'scarf',     role: 'Sharpens the idea' },
  'market-researcher':  { color: '#7fb6c9', prop: 'antenna',   role: 'Researches the market' },
  'spec-reviewer':      { color: '#a98bd6', prop: 'clipboard', role: 'Reviews specs' },
  'design-auditor':     { color: '#d98fc0', prop: 'beret',     role: 'Audits designs' },
  'ui-critic':          { color: '#f0a3a0', prop: 'bow',       role: 'Critiques screens' },
  architect:            { color: '#8796d8', prop: 'tophat',    role: 'Chooses the stack' },
  'license-auditor':    { color: '#b9a37a', prop: 'book',      role: 'Checks licenses' },
  'spike-runner':       { color: '#f2c94c', prop: 'propeller', role: 'Runs spikes' },
  'feature-builder':    { color: '#ef8354', prop: 'hardhat',   role: 'Builds features' },
  'code-reviewer':      { color: '#6c9bd2', prop: 'glasses',   role: 'Reviews code' },
  'security-auditor':   { color: '#7a8aa0', prop: 'shield',    role: 'Audits security' },
  'a11y-auditor':       { color: '#5cbfa7', prop: 'beanie',    role: 'Audits accessibility' },
  'perf-analyst':       { color: '#9cc76b', prop: 'headband',  role: 'Measures performance' },
  'qa-runner':          { color: '#ec8fb1', prop: 'cap',       role: 'Runs end-to-end tests' },
  'stuck-resolver':     { color: '#f4d58d', prop: 'halo',      role: 'Gets work unstuck' },
  'release-manager':    { color: '#6fc3c9', prop: 'flag',      role: 'Prepares releases' },
};
window.BMA_CAST_DEFAULT = { color: '#a7a1b5', prop: 'none', role: 'Helper' };
window.bmaCast = (type) => window.BMA_CAST[type] || window.BMA_CAST_DEFAULT;
