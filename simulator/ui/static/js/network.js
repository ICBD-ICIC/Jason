// ── network.js ────────────────────────────────────────────────────────────────
// Network editor: topology cards, parameter form, edge generators, canvas preview.

// ── Topology registry ─────────────────────────────────────────────────────────
const TOPOLOGIES = [
  {
    id: 'random',
    name: 'Random (ER)',
    desc: 'Erdős–Rényi random graph',
    params: ['p', 'directed', 'self_loops', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="10" cy="18" r="4" fill="#5b8df6" opacity=".8"/>
      <circle cx="26" cy="7"  r="4" fill="#5b8df6" opacity=".8"/>
      <circle cx="26" cy="29" r="4" fill="#5b8df6" opacity=".8"/>
      <circle cx="42" cy="18" r="4" fill="#5b8df6" opacity=".8"/>
      <line x1="14" y1="18" x2="22" y2="10" stroke="#3dffd0" stroke-width="1.2" opacity=".6"/>
      <line x1="14" y1="18" x2="22" y2="26" stroke="#3dffd0" stroke-width="1.2" opacity=".6"/>
      <line x1="30" y1="10" x2="38" y2="16" stroke="#3dffd0" stroke-width="1.2" opacity=".6"/>
      <line x1="30" y1="26" x2="38" y2="20" stroke="#3dffd0" stroke-width="1.2" opacity=".6"/>
    </svg>`,
  },
  {
    id: 'small_world',
    name: 'Small World',
    desc: 'Watts–Strogatz model',
    params: ['k', 'p', 'directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="26" cy="18" r="14" stroke="#2a3045" stroke-width="1"/>
      <circle cx="26" cy="4"  r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="38" cy="11" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="38" cy="25" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="26" cy="32" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="14" cy="25" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="14" cy="11" r="3.5" fill="#3dffd0" opacity=".85"/>
      <line x1="26" y1="7"  x2="35" y2="12" stroke="#3dffd0" stroke-width="1.2" opacity=".5"/>
      <line x1="35" y1="14" x2="35" y2="22" stroke="#3dffd0" stroke-width="1.2" opacity=".5"/>
      <line x1="35" y1="24" x2="26" y2="29" stroke="#3dffd0" stroke-width="1.2" opacity=".5"/>
      <line x1="24" y1="29" x2="16" y2="24" stroke="#3dffd0" stroke-width="1.2" opacity=".5"/>
      <line x1="15" y1="22" x2="15" y2="14" stroke="#3dffd0" stroke-width="1.2" opacity=".5"/>
      <line x1="17" y1="11" x2="24" y2="7"  stroke="#3dffd0" stroke-width="1.2" opacity=".5"/>
      <line x1="26" y1="7"  x2="35" y2="24" stroke="#5b8df6" stroke-width="1"   opacity=".5"/>
    </svg>`,
  },
  {
    id: 'scale_free',
    name: 'Scale-Free',
    desc: 'Barabási–Albert model',
    params: ['m', 'directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="26" cy="18" r="7" fill="#ff6b6b" opacity=".7"/>
      <circle cx="8"  cy="10" r="3.5" fill="#5b8df6" opacity=".8"/>
      <circle cx="44" cy="10" r="3.5" fill="#5b8df6" opacity=".8"/>
      <circle cx="8"  cy="26" r="3.5" fill="#5b8df6" opacity=".8"/>
      <circle cx="44" cy="26" r="3.5" fill="#5b8df6" opacity=".8"/>
      <circle cx="26" cy="3"  r="2.5" fill="#3dffd0" opacity=".7"/>
      <circle cx="26" cy="33" r="2.5" fill="#3dffd0" opacity=".7"/>
      <line x1="11" y1="11" x2="20" y2="15" stroke="#ff6b6b" stroke-width="1.4" opacity=".6"/>
      <line x1="41" y1="11" x2="32" y2="15" stroke="#ff6b6b" stroke-width="1.4" opacity=".6"/>
      <line x1="11" y1="25" x2="20" y2="21" stroke="#ff6b6b" stroke-width="1.4" opacity=".6"/>
      <line x1="41" y1="25" x2="32" y2="21" stroke="#ff6b6b" stroke-width="1.4" opacity=".6"/>
      <line x1="26" y1="5"  x2="26" y2="11" stroke="#ff6b6b" stroke-width="1.4" opacity=".6"/>
      <line x1="26" y1="31" x2="26" y2="25" stroke="#ff6b6b" stroke-width="1.4" opacity=".6"/>
    </svg>`,
  },
  {
    id: 'ring',
    name: 'Ring',
    desc: 'Each agent connected to nearest k neighbors',
    params: ['k', 'directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="26" cy="18" r="13" stroke="#2a3045" stroke-width="1"/>
      <circle cx="26" cy="5"  r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="37" cy="12" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="37" cy="24" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="26" cy="31" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="15" cy="24" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="15" cy="12" r="3.5" fill="#3dffd0" opacity=".85"/>
      <line x1="26" y1="8"  x2="34" y2="13" stroke="#3dffd0" stroke-width="1.4" opacity=".7"/>
      <line x1="34" y1="15" x2="34" y2="21" stroke="#3dffd0" stroke-width="1.4" opacity=".7"/>
      <line x1="34" y1="23" x2="26" y2="28" stroke="#3dffd0" stroke-width="1.4" opacity=".7"/>
      <line x1="24" y1="28" x2="17" y2="23" stroke="#3dffd0" stroke-width="1.4" opacity=".7"/>
      <line x1="16" y1="21" x2="16" y2="15" stroke="#3dffd0" stroke-width="1.4" opacity=".7"/>
      <line x1="17" y1="13" x2="24" y2="8"  stroke="#3dffd0" stroke-width="1.4" opacity=".7"/>
    </svg>`,
  },
  {
    id: 'complete',
    name: 'Complete',
    desc: 'All agents connected to all others',
    params: ['directed', 'self_loops', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="26" cy="5"  r="3.5" fill="#f0a500" opacity=".85"/>
      <circle cx="40" cy="26" r="3.5" fill="#f0a500" opacity=".85"/>
      <circle cx="12" cy="26" r="3.5" fill="#f0a500" opacity=".85"/>
      <line x1="26" y1="8"  x2="37" y2="23" stroke="#f0a500" stroke-width="1.2" opacity=".5"/>
      <line x1="26" y1="8"  x2="15" y2="23" stroke="#f0a500" stroke-width="1.2" opacity=".5"/>
      <line x1="15" y1="26" x2="37" y2="26" stroke="#f0a500" stroke-width="1.2" opacity=".5"/>
    </svg>`,
  },
  {
    id: 'star',
    name: 'Star',
    desc: 'One hub connected to all agents',
    params: ['directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="26" cy="18" r="5" fill="#f0a500" opacity=".9"/>
      <circle cx="26" cy="4"  r="3" fill="#5b8df6" opacity=".8"/>
      <circle cx="42" cy="18" r="3" fill="#5b8df6" opacity=".8"/>
      <circle cx="26" cy="32" r="3" fill="#5b8df6" opacity=".8"/>
      <circle cx="10" cy="18" r="3" fill="#5b8df6" opacity=".8"/>
      <line x1="26" y1="13" x2="26" y2="7"  stroke="#f0a500" stroke-width="1.5" opacity=".7"/>
      <line x1="31" y1="18" x2="39" y2="18" stroke="#f0a500" stroke-width="1.5" opacity=".7"/>
      <line x1="26" y1="23" x2="26" y2="29" stroke="#f0a500" stroke-width="1.5" opacity=".7"/>
      <line x1="21" y1="18" x2="13" y2="18" stroke="#f0a500" stroke-width="1.5" opacity=".7"/>
    </svg>`,
  },
  {
    id: 'bipartite',
    name: 'Bipartite',
    desc: 'Two groups, edges only between groups',
    params: ['p', 'directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="10" r="3.5" fill="#5b8df6" opacity=".85"/>
      <circle cx="12" cy="22" r="3.5" fill="#5b8df6" opacity=".85"/>
      <circle cx="40" cy="7"  r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="40" cy="18" r="3.5" fill="#3dffd0" opacity=".85"/>
      <circle cx="40" cy="29" r="3.5" fill="#3dffd0" opacity=".85"/>
      <line x1="15" y1="10" x2="37" y2="9"  stroke="#7a82a0" stroke-width="1.1" opacity=".6"/>
      <line x1="15" y1="10" x2="37" y2="18" stroke="#7a82a0" stroke-width="1.1" opacity=".6"/>
      <line x1="15" y1="22" x2="37" y2="18" stroke="#7a82a0" stroke-width="1.1" opacity=".6"/>
      <line x1="15" y1="22" x2="37" y2="28" stroke="#7a82a0" stroke-width="1.1" opacity=".6"/>
    </svg>`,
  },
  {
    id: 'custom',
    name: 'Manual',
    desc: 'Edit edges directly in the table',
    params: [],
    icon: `<svg viewBox="0 0 52 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="6" y="6" width="16" height="24" rx="3" fill="none" stroke="#7a82a0" stroke-width="1.4"/>
      <line x1="10" y1="13" x2="18" y2="13" stroke="#7a82a0" stroke-width="1.2"/>
      <line x1="10" y1="18" x2="18" y2="18" stroke="#7a82a0" stroke-width="1.2"/>
      <line x1="10" y1="23" x2="14" y2="23" stroke="#7a82a0" stroke-width="1.2"/>
      <circle cx="38" cy="10" r="4" fill="#5b8df6" opacity=".7"/>
      <circle cx="38" cy="26" r="4" fill="#3dffd0" opacity=".7"/>
      <line x1="38" y1="14" x2="38" y2="22" stroke="#5b8df6" stroke-width="1.4" opacity=".6"/>
    </svg>`,
  },
];

// Current topology selection and parameters
let selectedTopo = 'random';
let topoParams   = { k: 4, p: 0.3, m: 2, directed: false, self_loops: false, weight_min: 1, weight_max: 1 };

// ── Canvas interaction state ──────────────────────────────────────────────────
const netView = {
  scale:     1,
  offsetX:   0,
  offsetY:   0,
  dragging:  false,
  lastX:     0,
  lastY:     0,
  positions: null,   // cached node positions in world space
};

// ── HTML builder ──────────────────────────────────────────────────────────────
function buildNetworkEditor(name) {
  const st         = initializers['network.csv'];
  const agentNames = getAllAgentNames();
  const hasAgents  = agentNames.length > 0;

  const agentBanner = hasAgents
    ? `<div class="agent-source-info">
        <div class="agent-source-box">
          <div><strong>${agentNames.length}</strong> agents detected from agent types</div>
          <div class="agent-chips">${agentNames.map(n => `<span class="agent-chip">${esc(n)}</span>`).join('')}</div>
        </div>
      </div>`
    : `<div class="agent-source-info">
        <div>No agent instances defined yet —
          <strong>add agent types with instances</strong> to get name auto-complete and topology generation,
          or type agent names manually.
        </div>
      </div>`;

  const topoCards = TOPOLOGIES.map(t => `
    <div class="topo-card ${selectedTopo === t.id ? 'selected' : ''}" onclick="selectTopo('${t.id}')">
      <div class="topo-icon">${t.icon}</div>
      <div class="topo-name">${t.name}</div>
      <div class="topo-desc">${t.desc}</div>
    </div>`).join('');

  const topo       = TOPOLOGIES.find(t => t.id === selectedTopo);
  const paramsHTML = buildTopoParamsForm(topo);

  const edgeRows = st.rows.map((row, ri) => {
    const fromInput = buildAgentInput(`net-from-${ri}`, row['from'] ?? '', agentNames, `setInitCell('network.csv',${ri},'from',this.value)`);
    const toInput   = buildAgentInput(`net-to-${ri}`,   row['to']   ?? '', agentNames, `setInitCell('network.csv',${ri},'to',this.value)`);
    return `<tr>
      <td class="td-idx">${ri + 1}</td>
      <td>${fromInput}</td>
      <td>${toInput}</td>
      <td><input type="text" value="${esc(row['weight'] ?? '')}" placeholder="default"
        oninput="setInitCell('network.csv',${ri},'weight',this.value)"
        style="background:var(--surface);border-color:transparent;font-family:var(--mono);font-size:.78rem;padding:5px 8px;"></td>
      <td><button class="btn-del-row" onclick="deleteInitRow('network.csv',${ri})">✕</button></td>
    </tr>`;
  }).join('') || `<tr><td colspan="5" class="no-rows">No edges yet — generate a topology or add manually</td></tr>`;

  const netFileOpts = options.initializer_csvs.includes('network.csv')
    ? '<option value="network.csv">network.csv (current)</option>'
    : options.initializer_csvs.map(f => `<option value="${f}">${f}</option>`).join('') || '<option value="">(none found)</option>';

  return `
    <div class="editor">
      <div class="ed-header">
        <div class="tag blue">initializer</div>
        <div>
          <h2>network.csv
            <small>Define the connections between agents. Writes to initializer/${name} on generate</small>
          </h2>
        </div>
      </div>

      ${agentBanner}

      <!-- Topology generator -->
      <div class="card">
        <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Topology Generator</h4></div>
        <div class="card-body">
          <div class="topo-grid">${topoCards}</div>
          <div id="topo-params-area">${paramsHTML}</div>
          <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
            ${selectedTopo !== 'custom' ? `
              <button class="btn-sm accent" onclick="generateTopology()"
                ${!hasAgents ? 'disabled title="Add agent instances first"' : ''}>
                Generate Network
              </button>
              <button class="btn-sm" onclick="appendTopology()"
                ${!hasAgents ? 'disabled' : ''}>
                + Append to existing
              </button>
            ` : ''}
            ${st.rows.length ? `<span class="info-badge">📊 ${st.rows.length} edges</span>` : ''}
          </div>
          <div class="net-preview-wrap" style="margin-top:14px">
            <div class="net-preview-bar">
              network preview <span id="net-preview-stats"></span>
              <div class="net-preview-controls">
                <button class="net-ctrl-btn" onclick="netZoom(0.2)"  title="Zoom in">+</button>
                <button class="net-ctrl-btn" onclick="netZoom(-0.2)" title="Zoom out">−</button>
                <button class="net-ctrl-btn" onclick="netResetView()" title="Reset view">⊡</button>
              </div>
            </div>
            <canvas id="net-canvas" height="260"></canvas>
          </div>
        </div>
      </div>

      <!-- Load from disk -->
      <div class="card">
        <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Load from disk</h4></div>
        <div class="card-body">
          <div class="load-row">
            <label>Existing file:</label>
            <select id="init-file-sel-network_csv">${netFileOpts}</select>
            <button class="btn-sm accent" onclick="loadInitFromDisk('network.csv')">Load</button>
          </div>
          <div class="csv-zone">
            <input type="file" accept=".csv" onchange="loadInitCsvUpload('network.csv',this)">
            Or upload a CSV — columns: <em>from, to, weight</em>
          </div>
        </div>
      </div>

      <!-- Edge table -->
      <div class="card">
        <div class="card-head">
          <div class="dot" style="background:#f0a500"></div>
          <h4>Edges — ${st.rows.length} total</h4>
          <div class="card-head-actions">
            ${hasAgents ? `<button class="btn-sm" onclick="sortEdgesAlpha()">Sort</button>` : ''}
          </div>
        </div>
        <div class="table-toolbar">
          <button class="btn-sm accent" onclick="addNetworkRow()">+ Add Edge</button>
          ${st.rows.length ? `<button class="btn-sm btn-clear" onclick="clearInitRows('network.csv')">Clear All</button>` : ''}
        </div>
        <div class="card-body">
          <div class="tbl-wrap">
            <table class="data-table">
              <thead><tr><th class="col-idx">#</th><th>from</th><th>to</th><th>weight</th><th class="col-del"></th></tr></thead>
              <tbody id="net-edge-tbody">${edgeRows}</tbody>
            </table>
          </div>
        </div>
      </div>
    </div>`;
}

// ── Autocomplete input for agent names ────────────────────────────────────────
function buildAgentInput(id, value, agentNames, oninput) {
  const listId = id + '-list';
  const opts   = agentNames.map(n => `<option value="${esc(n)}">`).join('');
  return `<input type="text" id="${id}" value="${esc(value)}" list="${listId}"
    oninput="${oninput}" placeholder="agent name"
    style="background:var(--surface);border-color:transparent;font-family:var(--mono);font-size:.78rem;padding:5px 8px;">
    <datalist id="${listId}">${opts}</datalist>`;
}

// ── Topology parameter form ───────────────────────────────────────────────────
function buildTopoParamsForm(topo) {
  if (!topo || topo.id === 'custom')
    return `<p style="font-size:.8rem;color:var(--muted);margin-bottom:14px;">Edit edges directly in the table below.</p>`;

  const p     = topoParams;
  const parts = [];

  if (topo.params.includes('k'))
    parts.push(`<div class="field"><label>k — neighbors per node</label>
      <input type="number" value="${p.k}" min="1"
        oninput="topoParams.k=+this.value"></div>`);

  if (topo.params.includes('p'))
    parts.push(`<div class="field"><label>p — rewire / edge probability</label>
      <input type="number" value="${p.p}" min="0" max="1" step="0.05"
        oninput="topoParams.p=+this.value"></div>`);

  if (topo.params.includes('m'))
    parts.push(`<div class="field"><label>m — edges per new node</label>
      <input type="number" value="${p.m}" min="1"
        oninput="topoParams.m=+this.value"></div>`);

  if (topo.params.includes('weight_min'))
    parts.push(`<div class="field"><label>weight min</label>
      <input type="number" value="${p.weight_min}" step="0.1"
        oninput="topoParams.weight_min=+this.value"></div>`);

  if (topo.params.includes('weight_max'))
    parts.push(`<div class="field"><label>weight max</label>
      <input type="number" value="${p.weight_max}" step="0.1"
        oninput="topoParams.weight_max=+this.value"></div>`);

  const checkboxes = [];
  if (topo.params.includes('directed'))
    checkboxes.push(`<label style="display:flex;align-items:center;gap:8px;font-size:.8rem;cursor:pointer;">
      <input type="checkbox" ${p.directed ? 'checked' : ''} onchange="topoParams.directed=this.checked"> Directed</label>`);
  if (topo.params.includes('self_loops'))
    checkboxes.push(`<label style="display:flex;align-items:center;gap:8px;font-size:.8rem;cursor:pointer;">
      <input type="checkbox" ${p.self_loops ? 'checked' : ''} onchange="topoParams.self_loops=this.checked"> Self-loops</label>`);

  const paramsGrid = parts.length > 0
    ? `<div class="topo-params" style="grid-template-columns:repeat(${Math.min(parts.length, 4)},1fr)">${parts.join('')}</div>`
    : '';
  const cboxRow = checkboxes.length > 0
    ? `<div style="display:flex;gap:18px;margin-bottom:14px;">${checkboxes.join('')}</div>`
    : '';

  return paramsGrid + cboxRow;
}

// ── Topology selection ────────────────────────────────────────────────────────
function selectTopo(id) {
  selectedTopo = id;
  renderMain();
}

// ── Edge generation ───────────────────────────────────────────────────────────
function randWeight() {
  const { weight_min: mn, weight_max: mx } = topoParams;
  if (mn === mx) return mn;
  return +(Math.random() * (mx - mn) + mn).toFixed(3);
}

function makeEdge(from, to) {
  const w = randWeight();
  const weightStr = (topoParams.weight_min === 1 && topoParams.weight_max === 1) ? '' : String(w);
  return { from, to, weight: weightStr };
}

function generateEdges(agents) {
  const edges = [];
  const n = agents.length;
  if (n === 0) return edges;

  const seen = new Set();
  const addEdge = (a, b) => {
    const key = topoParams.directed ? `${a}|${b}` : [a, b].sort().join('|');
    if (!seen.has(key)) {
      seen.add(key);
      edges.push(makeEdge(agents[a], agents[b]));
    }
  };

  switch (selectedTopo) {

    // ── RANDOM ─────────────────────────────────────────
    case 'random': {
      for (let i = 0; i < n; i++) {
        for (let j = (topoParams.directed ? 0 : i + 1); j < n; j++) {
          if (i === j && !topoParams.self_loops) continue;
          if (Math.random() < topoParams.p) addEdge(i, j);
          if (topoParams.directed && i !== j && Math.random() < topoParams.p) {
            addEdge(j, i);
          }
        }
      }
      break;
    }

    // ── SMALL WORLD (Watts–Strogatz simplificado) ──────
    case 'small_world': {
      const k = Math.max(1, Math.floor(topoParams.k / 2));

      // base ring
      for (let i = 0; i < n; i++) {
        for (let d = 1; d <= k; d++) {
          const j = (i + d) % n;
          addEdge(i, j);
          if (topoParams.directed) addEdge(j, i);
        }
      }

      // rewiring
      const currentEdges = [...edges];
      edges.length = 0;
      seen.clear();

      for (const e of currentEdges) {
        const a = agents.indexOf(e.from);
        let b = agents.indexOf(e.to);

        if (Math.random() < topoParams.p) {
          let newB, tries = 0;
          do {
            newB = Math.floor(Math.random() * n);
            tries++;
          } while ((newB === a || seen.has(`${a}|${newB}`)) && tries < 50);

          if (tries < 50) b = newB;
        }

        addEdge(a, b);
      }

      break;
    }

    // ── SCALE FREE (Barabási–Albert) ──────────────────
    case 'scale_free': {
      const m = Math.max(1, Math.min(topoParams.m, n - 1));
      const degree = new Array(n).fill(0);

      // fully connected seed
      for (let i = 0; i < m; i++) {
        for (let j = i + 1; j < m; j++) {
          addEdge(i, j);
          degree[i]++;
          degree[j]++;
        }
      }

      // growth
      for (let i = m; i < n; i++) {
        const targets = new Set();

        while (targets.size < m) {
          const totalDeg = degree.reduce((a, b) => a + b, 0) || 1;
          let r = Math.random() * totalDeg;
          let acc = 0;

          for (let j = 0; j < i; j++) {
            acc += degree[j];
            if (acc >= r) {
              targets.add(j);
              break;
            }
          }
        }

        for (const t of targets) {
          addEdge(t, i);
          degree[t]++;
          degree[i]++;
        }
      }

      if (topoParams.directed) {
        const extra = [];
        for (const e of edges) {
          const a = agents.indexOf(e.from);
          const b = agents.indexOf(e.to);
          extra.push([b, a]);
        }
        for (const [a, b] of extra) addEdge(a, b);
      }

      break;
    }

    // ── RING ──────────────────────────────────────────
    case 'ring': {
      const k = Math.max(1, Math.floor(topoParams.k / 2));

      for (let i = 0; i < n; i++) {
        for (let d = 1; d <= k; d++) {
          const j = (i + d) % n;
          addEdge(i, j);
          if (topoParams.directed) addEdge(j, i);
        }
      }
      break;
    }

    // ── COMPLETE ──────────────────────────────────────
    case 'complete': {
      for (let i = 0; i < n; i++) {
        for (let j = (topoParams.directed ? 0 : i + 1); j < n; j++) {
          if (i === j && !topoParams.self_loops) continue;
          addEdge(i, j);
        }
      }
      break;
    }

    // ── STAR ──────────────────────────────────────────
    case 'star': {
      const hub = Math.floor(Math.random() * n);

      for (let i = 0; i < n; i++) {
        if (i === hub) continue;
        addEdge(hub, i);
        if (topoParams.directed) addEdge(i, hub);
      }
      break;
    }

    // ── BIPARTITE ─────────────────────────────────────
    case 'bipartite': {
      const half = Math.floor(n / 2);

      for (let i = 0; i < half; i++) {
        for (let j = half; j < n; j++) {
          if (Math.random() < topoParams.p) {
            addEdge(i, j);
            if (topoParams.directed) addEdge(j, i);
          }
        }
      }
      break;
    }
  }

  if (!topoParams.directed) {
    const existing = new Set(edges.map(e => `${e.from}|${e.to}`));
    const reversed = edges
      .filter(e => !existing.has(`${e.to}|${e.from}`))
      .map(e => makeEdge(e.to, e.from));
    edges.push(...reversed);
  }
  return edges;
}

// ── Public actions ────────────────────────────────────────────────────────────
function generateTopology() {
  const agents = getAllAgentNames();
  if (agents.length === 0) { showToast('No agent instances found. Add agent types with instances first.'); return; }
  initializers['network.csv'].rows = generateEdges(agents);
  netView.positions = null; // force recompute layout
  renderInitNav();
  renderMain();
  setTimeout(() => { netResetView(); drawNetPreview(); }, 80);
}

function appendTopology() {
  const agents = getAllAgentNames();
  if (agents.length === 0) { showToast('No agent instances found.'); return; }
  initializers['network.csv'].rows.push(...generateEdges(agents));
  netView.positions = null;
  renderInitNav();
  renderMain();
  setTimeout(() => { netResetView(); drawNetPreview(); }, 80);
}

function addNetworkRow() {
  initializers['network.csv'].rows.push({ from: '', to: '', weight: '' });
  renderMain();
  renderInitNav();
  setTimeout(() => drawNetPreview(), 80);
}

function sortEdgesAlpha() {
  initializers['network.csv'].rows.sort((a, b) => (a.from + a.to).localeCompare(b.from + b.to));
  renderMain();
  setTimeout(() => drawNetPreview(), 80);
}

// ── View controls ─────────────────────────────────────────────────────────────
function netZoom(delta) {
  netView.scale = Math.min(8, Math.max(0.1, netView.scale + delta));
  drawNetPreview();
}

function netResetView() {
  netView.scale   = 1;
  netView.offsetX = 0;
  netView.offsetY = 0;
  drawNetPreview();
}

function _setupCanvasInteraction(canvas) {
  // Avoid attaching duplicate listeners by tagging the canvas
  if (canvas._netInteractive) return;
  canvas._netInteractive = true;

  // Wheel zoom — zoom toward cursor position
  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    const rect  = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const delta  = e.deltaY < 0 ? 0.15 : -0.15;
    const oldScale = netView.scale;
    netView.scale  = Math.min(8, Math.max(0.1, oldScale + delta));
    // Adjust offset so zoom is centered on cursor
    const scaleDiff = netView.scale - oldScale;
    netView.offsetX -= mouseX * scaleDiff;
    netView.offsetY -= mouseY * scaleDiff;
    drawNetPreview();
  }, { passive: false });

  // Pan — click and drag
  canvas.addEventListener('mousedown', e => {
    netView.dragging = true;
    netView.lastX    = e.clientX;
    netView.lastY    = e.clientY;
    canvas.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', e => {
    if (!netView.dragging) return;
    netView.offsetX += e.clientX - netView.lastX;
    netView.offsetY += e.clientY - netView.lastY;
    netView.lastX    = e.clientX;
    netView.lastY    = e.clientY;
    drawNetPreview();
  });

  window.addEventListener('mouseup', () => {
    if (netView.dragging) {
      netView.dragging = false;
      const canvas = document.getElementById('net-canvas');
      if (canvas) canvas.style.cursor = 'grab';
    }
  });

  // Touch pan + pinch zoom
  let lastTouchDist = null;
  canvas.addEventListener('touchstart', e => {
    if (e.touches.length === 1) {
      netView.dragging = true;
      netView.lastX    = e.touches[0].clientX;
      netView.lastY    = e.touches[0].clientY;
    }
    if (e.touches.length === 2) {
      netView.dragging = false;
      lastTouchDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }
  }, { passive: true });

  canvas.addEventListener('touchmove', e => {
    e.preventDefault();
    if (e.touches.length === 1 && netView.dragging) {
      netView.offsetX += e.touches[0].clientX - netView.lastX;
      netView.offsetY += e.touches[0].clientY - netView.lastY;
      netView.lastX    = e.touches[0].clientX;
      netView.lastY    = e.touches[0].clientY;
      drawNetPreview();
    }
    if (e.touches.length === 2 && lastTouchDist !== null) {
      const dist  = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      netView.scale = Math.min(8, Math.max(0.1, netView.scale * (dist / lastTouchDist)));
      lastTouchDist = dist;
      drawNetPreview();
    }
  }, { passive: false });

  canvas.addEventListener('touchend', () => {
    netView.dragging  = false;
    lastTouchDist     = null;
  });
}

// ── Canvas preview ────────────────────────────────────────────────────────────
function drawNetPreview() {
  const canvas = document.getElementById('net-canvas');
  if (!canvas) return;

  _setupCanvasInteraction(canvas);
  canvas.style.cursor = netView.dragging ? 'grabbing' : 'grab';

  const dpr = window.devicePixelRatio || 1;
  const W   = canvas.offsetWidth;
  const H   = canvas.offsetHeight || 260;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.fillStyle = '#0a0c10';
  ctx.fillRect(0, 0, W, H);

  const st         = initializers['network.csv'];
  const agentNames = getAllAgentNames();

  // Collect nodes
  const nodeSet = new Set(agentNames);
  for (const r of st.rows) {
    if (r.from) nodeSet.add(r.from);
    if (r.to)   nodeSet.add(r.to);
  }
  const nodes = [...nodeSet];

  if (nodes.length === 0) {
    ctx.fillStyle = '#7a82a0';
    ctx.font      = '12px DM Sans, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No nodes yet', W / 2, H / 2);
    const statsEl = document.getElementById('net-preview-stats');
    if (statsEl) statsEl.textContent = '';
    return;
  }

  // Compute world-space positions once (or when nodes change)
  const nodeKey = nodes.join('|');
  if (!netView.positions || netView.positions._key !== nodeKey) {
    const margin    = 40;
    const angleStep = (2 * Math.PI) / nodes.length;
    const rx        = (W / 2 - margin);
    const ry        = (H / 2 - margin);
    const pos       = { _key: nodeKey };
    nodes.forEach((n, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      pos[n] = { x: W / 2 + rx * Math.cos(angle), y: H / 2 + ry * Math.sin(angle) };
    });
    netView.positions = pos;
  }

  const pos = netView.positions;

  // Apply pan + zoom transform
  ctx.save();
  ctx.translate(netView.offsetX, netView.offsetY);
  ctx.scale(netView.scale, netView.scale);

  // Draw edges
  for (const r of st.rows) {
    if (!r.from || !r.to || !pos[r.from] || !pos[r.to]) continue;
    const { x: x1, y: y1 } = pos[r.from];
    const { x: x2, y: y2 } = pos[r.to];

    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = 'rgba(91,141,246,0.35)';
    ctx.lineWidth   = 1.2 / netView.scale;
    ctx.stroke();

    // Arrowhead
    const dx = x2 - x1, dy = y2 - y1, len = Math.sqrt(dx * dx + dy * dy);
    if (len > 0) {
      const ux = dx / len, uy = dy / len;
      const ax = x2 - ux * 6, ay = y2 - uy * 6;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - ux * 6 + uy * 3, ay - uy * 6 - ux * 3);
      ctx.lineTo(ax - ux * 6 - uy * 3, ay - uy * 6 + ux * 3);
      ctx.closePath();
      ctx.fillStyle = 'rgba(91,141,246,0.5)';
      ctx.fill();
    }
  }

  // Draw nodes
  const nodeRadius = Math.max(4, Math.min(9, 140 / nodes.length));
  nodes.forEach(n => {
    const { x, y }  = pos[n];
    const isKnown   = agentNames.includes(n);
    ctx.beginPath();
    ctx.arc(x, y, nodeRadius, 0, Math.PI * 2);
    ctx.fillStyle   = isKnown ? 'rgba(61,255,208,0.85)' : 'rgba(91,141,246,0.6)';
    ctx.strokeStyle = isKnown ? 'rgba(61,255,208,0.4)'  : 'rgba(91,141,246,0.3)';
    ctx.lineWidth   = 1 / netView.scale;
    ctx.fill();
    ctx.stroke();

    if (nodes.length <= 40) {
      ctx.fillStyle    = '#e8ecf5';
      ctx.font         = `${Math.max(8, Math.min(11, 100 / nodes.length)) / netView.scale}px Space Mono, monospace`;
      ctx.textAlign    = 'center';
      ctx.textBaseline = 'middle';
      const labelR = nodeRadius + 8 / netView.scale;
      const angle  = Math.atan2(y - H / 2, x - W / 2);
      ctx.fillText(
        n.length > 10 ? n.slice(0, 9) + '…' : n,
        x + Math.cos(angle) * labelR,
        y + Math.sin(angle) * labelR
      );
    }
  });

  ctx.restore();

  // Stats bar (outside transform)
  const statsEl = document.getElementById('net-preview-stats');
  if (statsEl) statsEl.textContent = `— ${nodes.length} nodes · ${st.rows.length} edges · ${Math.round(netView.scale * 100)}%`;
}