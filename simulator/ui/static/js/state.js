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
 * Respects _count: a row with _count=3 expands to stem_N_1, stem_N_2, stem_N_3
 * so that network/profiles editors show the actual agent names.
 */
function getAllAgentNames() {
  const names = [];
  const stemCounters = {};

  for (const t of types) {
    if (!t.asl || !t.instances.length) continue;
    const stem = t.asl.replace(/\.asl$/, '');

    // Count total instances for this stem to decide whether to suffix
    const stemTotal = t.instances.reduce((s, inst) => s + (parseInt(inst._count) || 1), 0);

    for (let ri = 0; ri < t.instances.length; ri++) {
      const inst  = t.instances[ri];
      const count = parseInt(inst._count) || 1;

      if (count === 1 && stemTotal === 1) {
        // Only one instance total, no suffix
        names.push(stem);
      } else if (count === 1) {
        // Single instance in this row — gets its own sequential name
        stemCounters[stem] = (stemCounters[stem] || 0) + 1;
        names.push(`${stem}_${stemCounters[stem]}`);
      } else {
        // Group row: expand count → stem_N_1 .. stem_N_count
        // The group itself gets one sequential index, then _1.._count within it
        stemCounters[stem] = (stemCounters[stem] || 0) + 1;
        const groupIdx = stemCounters[stem];
        for (let i = 1; i <= count; i++) {
          names.push(`${stem}_${groupIdx}_${i}`);
        }
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
