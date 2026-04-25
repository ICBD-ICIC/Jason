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

/**
 * Collect all agent instance names derived from defined types.
 * Each group row with _count=N expands into N individually-named agents:
 *   stem_1, stem_2, ... stem_N  (sequential across all rows for the same stem)
 * Single-stem-single-instance → no suffix.
 */
function getAllAgentNames() {
  const names = [];
  const stemCounters = {};

  // Pre-count total agents per stem to decide whether to use suffixes
  const stemTotals = {};
  for (const t of types) {
    if (!t.asl || !t.instances.length) continue;
    const stem = t.asl.replace(/\.asl$/, '');
    for (const inst of t.instances) {
      const count = parseInt(inst._count) || 1;
      stemTotals[stem] = (stemTotals[stem] || 0) + count;
    }
  }

  for (const t of types) {
    if (!t.asl || !t.instances.length) continue;
    const stem = t.asl.replace(/\.asl$/, '');
    const multipleTotal = (stemTotals[stem] || 1) > 1;

    for (const inst of t.instances) {
      const count = parseInt(inst._count) || 1;
      for (let i = 0; i < count; i++) {
        stemCounters[stem] = (stemCounters[stem] || 0) + 1;
        const idx = stemCounters[stem];
        names.push(multipleTotal ? `${stem}_${idx}` : stem);
      }
    }
  }

  return names;
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

/** Sidebar tab switching */
function switchTab(tab) {
  currentTab = tab;
  ['agents', 'init'].forEach(t => {
    $(`#tab-${t}`).classList.toggle('active', t === tab);
    $(`#sb-${t}`).classList.toggle('sb-panel--active', t === tab);
  });
  if (tab === 'agents') {
    activeInit = null;
  } else {
    activeTypeId = null;
    if (!activeInit) activeInit = INIT_NAMES[0];
    renderInitNav();
  }
  renderMain();
}