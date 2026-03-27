// state.js — global app state + boot

let options = { asl_files: [], arch_classes: [], bb_classes: [], initializer_schemas: {} };
let types        = [];   // [{id, asl, arch_class, bb_class, columns, instances}]
let activeTypeId = null;
let activeInit   = null;
let currentTab   = 'agents';
let uid          = 0;
let pendingColTypeId = null;

const INIT_NAMES = ['messages.csv', 'network.csv', 'public_profiles.csv'];
let initializers = {};

// Collect all agent instance names from defined types
function getAllAgentNames() {
  return types.flatMap(t => {
    if (!t.asl || !t.instances.length) return [];
    const stem = t.asl.replace(/\.asl$/, '');
    return t.instances.map((_, i) => `${stem}_${i + 1}`);
  });
}

// Boot: fetch server options, seed initializer state
(async () => {
  try {
    const r = await fetch('/api/options');
    options = await r.json();
    for (const name of INIT_NAMES) {
      initializers[name] = { rows: [], schema: options.initializer_schemas[name] || [] };
    }
    renderInitNav();
  } catch {
    showToast('Cannot reach server. Is Flask running?');
  }
})();

// Sidebar tab switching
function switchTab(tab) {
  currentTab = tab;
  ['agents', 'init'].forEach(t => {
    $(`#tab-${t}`).classList.toggle('active', t === tab);
    $(`#sb-${t}`).classList.toggle('sb-panel--active', t === tab);
  });
  if (tab === 'agents') { activeInit = null; }
  else { activeTypeId = null; if (!activeInit) activeInit = INIT_NAMES[0]; renderInitNav(); }
  renderMain();
}
