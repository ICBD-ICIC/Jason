// ── state.js ─────────────────────────────────────────────────────────────────
// Global application state and boot logic.
// All other modules read/write these variables directly (single-page app pattern).

// Server options fetched on boot
let options = {
  asl_files: [],
  arch_classes: [],
  bb_classes: [],
  initializer_csvs: [],
  initializer_schemas: {},
};

// Agent types defined by the user
let types        = [];   // [{id, asl, arch_class, bb_class, columns:[], instances:[]}]
let activeTypeId = null;
let uid          = 0;
let pendingColTypeId = null;

// Initializer CSV state
const INIT_NAMES = ['messages.csv', 'network.csv', 'public_profiles.csv'];
let initializers = {};   // { [name]: { rows, schema, dirty } }
let activeInit   = null;

// Current sidebar tab
let currentTab = 'agents';

// ── Boot ──────────────────────────────────────────────────────────────────────
(async () => {
  try {
    const r = await fetch('/api/options');
    options = await r.json();
    for (const name of INIT_NAMES) {
      initializers[name] = {
        rows:   [],
        schema: options.initializer_schemas[name] || [],
        dirty:  false,
      };
    }
    renderInitNav();
  } catch {
    showToast('Cannot reach server. Is Flask running?');
  }
})();

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-agents').classList.toggle('active', tab === 'agents');
  document.getElementById('tab-init').classList.toggle('active',   tab === 'init');
  document.getElementById('sb-agents').style.display = tab === 'agents' ? 'flex' : 'none';
  document.getElementById('sb-init').style.display   = tab === 'init'   ? 'flex' : 'none';

  if (tab === 'agents') {
    activeInit = null;
    renderMain();
  } else {
    activeTypeId = null;
    if (!activeInit) activeInit = INIT_NAMES[0];
    renderInitNav();
    renderMain();
  }
}

// ── Shared helper: collect all agent names from defined types ─────────────────
function getAllAgentNames() {
  const names = new Set();
  for (const t of types) {
    for (const inst of t.instances) {
      const name = inst['name'] || inst['agent'] || inst['id'] || inst['agent_name'];
      if (name && name.trim()) names.add(name.trim());
    }
    if (t.asl) {
      const stem = t.asl.replace(/\.asl$/, '');
      if (t.instances.length === 0) names.add(stem);
      for (let i = 1; i <= t.instances.length; i++) names.add(`${stem}_${i}`);
    }
  }
  return [...names];
}
