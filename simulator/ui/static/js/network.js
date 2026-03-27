// network.js — network editor: topology generator, manual mode, canvas preview

// ── Topology registry ─────────────────────────────────────────────────────────

const TOPOLOGIES = [
  {
    id: 'random', name: 'Random (ER)', desc: 'Erdős–Rényi random graph',
    params: ['p', 'directed', 'self_loops', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none">
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
    id: 'small_world', name: 'Small World', desc: 'Watts–Strogatz model',
    params: ['k', 'p', 'directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none">
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
    id: 'scale_free', name: 'Scale-Free', desc: 'Barabási–Albert model',
    params: ['m', 'directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none">
      <circle cx="26" cy="18" r="7"   fill="#ff6b6b" opacity=".7"/>
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
    id: 'ring', name: 'Ring', desc: 'Each agent connected to nearest k neighbors',
    params: ['k', 'directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none">
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
    id: 'complete', name: 'Complete', desc: 'All agents connected to all others',
    params: ['directed', 'self_loops', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none">
      <circle cx="26" cy="5"  r="3.5" fill="#f0a500" opacity=".85"/>
      <circle cx="40" cy="26" r="3.5" fill="#f0a500" opacity=".85"/>
      <circle cx="12" cy="26" r="3.5" fill="#f0a500" opacity=".85"/>
      <line x1="26" y1="8"  x2="37" y2="23" stroke="#f0a500" stroke-width="1.2" opacity=".5"/>
      <line x1="26" y1="8"  x2="15" y2="23" stroke="#f0a500" stroke-width="1.2" opacity=".5"/>
      <line x1="15" y1="26" x2="37" y2="26" stroke="#f0a500" stroke-width="1.2" opacity=".5"/>
    </svg>`,
  },
  {
    id: 'star', name: 'Star', desc: 'One hub connected to all agents',
    params: ['directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none">
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
    id: 'bipartite', name: 'Bipartite', desc: 'Two groups, edges only between groups',
    params: ['p', 'directed', 'weight_min', 'weight_max'],
    icon: `<svg viewBox="0 0 52 36" fill="none">
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
];

// ── State ─────────────────────────────────────────────────────────────────────

let selectedTopo = 'random';
let topoParams   = { k: 4, p: 0.3, m: 2, directed: false, self_loops: false, weight_min: 1, weight_max: 1 };
let netMode      = 'generator';

const netView = { scale: 1, offsetX: 0, offsetY: 0, dragging: false, lastX: 0, lastY: 0, positions: null };

let netPreviewHeight = 220;
let _resizing = false, _resizeStartY = 0, _resizeStartH = 0;

const VIRT_ROW_H  = 34;
const VIRT_OVERSCAN = 8;

// ── Main HTML builder ─────────────────────────────────────────────────────────

function buildNetworkEditor(name) {
  const st     = initializers['network.csv'];
  const agents = getAllAgentNames();

  const agentBanner = `
    <div class="agent-source-info">
      ${agents.length
        ? `<div class="agent-source-box">
            <div><strong>${agents.length}</strong> agent${agents.length !== 1 ? 's' : ''} detected from defined types</div>
            <div class="agent-chips">${agents.map(n => `<span class="agent-chip">${esc(n)}</span>`).join('')}</div>
           </div>`
        : `<div>No agent instances yet — <strong>add types with instances</strong> to enable topology generation.</div>`
      }
    </div>`;

  return `
    <div class="editor">
      <div class="ed-header">
        <div class="tag blue">initializer</div>
        <h2>network.csv<small>Define connections · written to initializer/${esc(name)} on generate</small></h2>
      </div>
      ${agentBanner}
      <div class="net-mode-tabs">
        <button class="net-mode-tab ${netMode === 'generator' ? 'active' : ''}" onclick="setNetMode('generator')">⚡ Topology Generator</button>
        <button class="net-mode-tab ${netMode === 'manual'    ? 'active' : ''}" onclick="setNetMode('manual')">✏️ Manual / Load File</button>
      </div>
      ${netMode === 'generator' ? buildGeneratorPanel(st, agents) : buildManualPanel()}
      ${buildPreview()}
      <div class="card">
        <div class="card-head">
          <div class="dot" style="background:#f0a500"></div>
          <h4>Edges — ${st.rows.length} total</h4>
          <div class="card-head-actions">
            ${agents.length ? `<button class="btn-sm" onclick="sortEdgesAlpha()">Sort</button>` : ''}
            ${st.rows.length ? `<button class="btn-sm btn-clear" onclick="clearNetRows()">Clear all</button>` : ''}
          </div>
        </div>
        <div class="table-toolbar">
          <button class="btn-sm accent" onclick="addNetworkRow()">+ Add edge</button>
        </div>
        <div class="card-body">${buildEdgeTable(st, agents)}</div>
      </div>
    </div>`;
}

// ── Sub-panels ────────────────────────────────────────────────────────────────

function buildGeneratorPanel(st, agents) {
  const topo = TOPOLOGIES.find(t => t.id === selectedTopo);
  return `
    <div class="card">
      <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Topology</h4></div>
      <div class="card-body">
        <div class="topo-grid">
          ${TOPOLOGIES.map(t => `
            <div class="topo-card ${selectedTopo === t.id ? 'selected' : ''}" onclick="selectTopo('${t.id}')">
              <div class="topo-icon">${t.icon}</div>
              <div class="topo-name">${t.name}</div>
              <div class="topo-desc">${t.desc}</div>
            </div>`).join('')}
        </div>
        <div id="topo-params-area">${buildTopoParamsForm(topo)}</div>
        <div class="net-gen-actions">
          <button class="btn-sm accent net-gen-btn" onclick="generateTopology()"
            ${!agents.length ? 'disabled title="Add agent instances first"' : ''}>⚡ Generate network</button>
          ${st.rows.length ? `<span class="net-gen-warning">⚠ Replaces ${st.rows.length} existing edges</span>` : ''}
          ${st.rows.length ? `<span class="info-badge">📊 ${st.rows.length} edges</span>` : ''}
        </div>
      </div>
    </div>`;
}

function buildManualPanel() {
  return `
    <div class="card">
      <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Load from file</h4></div>
      <div class="card-body">
        <div class="csv-zone">
          <input type="file" accept=".csv" onchange="loadInitCsvUpload('network.csv',this)">
          Upload a CSV — columns: <em>from, to, weight</em>
        </div>
        <p style="font-size:.77rem;color:var(--muted);margin-top:4px;">You can also add edges manually in the table below.</p>
      </div>
    </div>`;
}

function buildPreview() {
  return `
    <div class="card net-preview-card">
      <div class="card-head">
        <div class="dot" style="background:var(--accent)"></div>
        <h4>Preview</h4>
        <span id="net-preview-stats" style="font-family:var(--mono);font-size:.68rem;color:var(--accent2);margin-left:4px;"></span>
        <div class="net-preview-controls" style="margin-left:auto">
          <button class="net-ctrl-btn" onclick="netZoom(0.2)"   title="Zoom in">+</button>
          <button class="net-ctrl-btn" onclick="netZoom(-0.2)"  title="Zoom out">−</button>
          <button class="net-ctrl-btn" onclick="netResetView()" title="Reset">⊡</button>
        </div>
      </div>
      <div class="net-preview-body" id="net-preview-body"
           style="height:${netPreviewHeight}px;min-height:120px;position:relative;background:#0a0c10;overflow:hidden;">
        <canvas id="net-canvas" style="display:block;width:100%;height:100%;cursor:grab;"></canvas>
      </div>
      <div class="net-resize-handle" id="net-resize-handle" title="Drag to resize"></div>
    </div>`;
}

// ── Edge table (virtual scroll) ───────────────────────────────────────────────

function buildEdgeTable(st, agents) {
  if (!st.rows.length) return `
    <div class="tbl-wrap"><table class="data-table">
      <thead><tr><th class="col-idx">#</th><th>from</th><th>to</th><th>weight</th><th class="col-del"></th></tr></thead>
      <tbody><tr><td colspan="5" class="no-rows">No edges yet — generate a topology, load a file, or add manually</td></tr></tbody>
    </table></div>`;

  const h = Math.max(120, Math.min(420, st.rows.length * VIRT_ROW_H + 40));
  return `
    <div class="virt-scroll-wrap" id="net-virt-wrap" style="height:${h}px;overflow-y:auto;" onscroll="onNetVirtScroll()">
      <table class="data-table" style="width:100%;table-layout:fixed;">
        <colgroup><col style="width:44px"><col><col><col style="width:110px"><col style="width:36px"></colgroup>
        <thead style="position:sticky;top:0;z-index:2;background:var(--card);">
          <tr><th class="col-idx">#</th><th>from</th><th>to</th><th>weight</th><th class="col-del"></th></tr>
        </thead>
      </table>
      <div style="position:relative;height:${st.rows.length * VIRT_ROW_H}px;">
        <table class="data-table" id="net-virt-table" style="width:100%;table-layout:fixed;position:absolute;top:0;left:0;">
          <colgroup><col style="width:44px"><col><col><col style="width:110px"><col style="width:36px"></colgroup>
          <tbody id="net-edge-tbody"></tbody>
        </table>
      </div>
    </div>`;
}

function initNetVirtScroll() { renderNetVirtRows(0); }

function onNetVirtScroll() {
  const wrap = $('#net-virt-wrap');
  if (wrap) renderNetVirtRows(wrap.scrollTop);
}

function renderNetVirtRows(scrollTop) {
  const tbody = $('#net-edge-tbody'), table = $('#net-virt-table');
  if (!tbody || !table) return;

  const st    = initializers['network.csv'];
  const agents = getAllAgentNames();
  const total = st.rows.length;
  const wrap  = $('#net-virt-wrap');
  const viewH = wrap?.clientHeight ?? 420;

  const first  = Math.floor(scrollTop / VIRT_ROW_H);
  const start  = Math.max(0, first - VIRT_OVERSCAN);
  const end    = Math.min(total - 1, first + Math.ceil(viewH / VIRT_ROW_H) + VIRT_OVERSCAN);

  table.style.top = (start * VIRT_ROW_H) + 'px';

  const inputStyle = `style="background:var(--surface);border-color:transparent;font-family:var(--mono);font-size:.78rem;padding:5px 8px;width:100%;"`;
  const rows = [];
  for (let ri = start; ri <= end; ri++) {
    const row = st.rows[ri];
    rows.push(`<tr style="height:${VIRT_ROW_H}px">
      <td class="td-idx">${ri + 1}</td>
      <td>${agentInput(`net-from-${ri}`, row.from ?? '', agents, `setInitCell('network.csv',${ri},'from',this.value)`)}</td>
      <td>${agentInput(`net-to-${ri}`,   row.to   ?? '', agents, `setInitCell('network.csv',${ri},'to',this.value)`)}</td>
      <td><input type="text" value="${esc(row.weight ?? '')}" placeholder="default"
        oninput="setInitCell('network.csv',${ri},'weight',this.value)" ${inputStyle}></td>
      <td><button class="btn-del-row" onclick="deleteNetRow(${ri})">✕</button></td>
    </tr>`);
  }
  tbody.innerHTML = rows.join('');
}

function deleteNetRow(ri) {
  initializers['network.csv'].rows.splice(ri, 1);
  renderInitNav();
  const h4 = $('#net-edge-tbody')?.closest('.card')?.querySelector('h4');
  if (h4) h4.textContent = `Edges — ${initializers['network.csv'].rows.length} total`;
  const wrap = $('#net-virt-wrap');
  renderNetVirtRows(wrap?.scrollTop ?? 0);
  setTimeout(drawNetPreview, 60);
}

// ── Mode / topology switching ─────────────────────────────────────────────────

function setNetMode(mode) {
  netMode = mode;
  renderMain();
  setTimeout(() => { _setupResizeHandle(); drawNetPreview(); initNetVirtScroll(); }, 60);
}

function selectTopo(id) {
  selectedTopo = id;
  renderMain();
  setTimeout(() => { _setupResizeHandle(); drawNetPreview(); initNetVirtScroll(); }, 60);
}

// ── Autocomplete input ────────────────────────────────────────────────────────

function agentInput(id, value, agents, oninput) {
  const listId = `${id}-list`;
  return `<input type="text" id="${id}" value="${esc(value)}" list="${listId}" oninput="${oninput}"
    placeholder="agent name" style="background:var(--surface);border-color:transparent;font-family:var(--mono);font-size:.78rem;padding:5px 8px;width:100%;">
    <datalist id="${listId}">${agents.map(n => `<option value="${esc(n)}">`).join('')}</datalist>`;
}

// ── Topology param form ───────────────────────────────────────────────────────

function buildTopoParamsForm(topo) {
  if (!topo) return '';
  const p = topoParams;

  const numField = (param, label, extra = '') =>
    topo.params.includes(param)
      ? `<div class="field"><label>${label}</label>
          <input type="number" value="${p[param]}" ${extra} oninput="topoParams.${param}=+this.value"></div>`
      : '';

  const checkbox = (param, label) =>
    topo.params.includes(param)
      ? `<label style="display:flex;align-items:center;gap:8px;font-size:.8rem;cursor:pointer;">
          <input type="checkbox" ${p[param] ? 'checked' : ''} onchange="topoParams.${param}=this.checked"> ${label}</label>`
      : '';

  const fields = [
    numField('k', 'k — neighbors per node', 'min="1"'),
    numField('p', 'p — rewire / edge probability', 'min="0" max="1" step="0.05"'),
    numField('m', 'm — edges per new node', 'min="1"'),
    numField('weight_min', 'weight min', 'step="0.1"'),
    numField('weight_max', 'weight max', 'step="0.1"'),
  ].filter(Boolean);

  const checkboxes = [checkbox('directed', 'Directed'), checkbox('self_loops', 'Self-loops')].filter(Boolean);

  const cols = Math.min(fields.length, 4) || 1;
  return (fields.length ? `<div class="topo-params" style="grid-template-columns:repeat(${cols},1fr)">${fields.join('')}</div>` : '')
       + (checkboxes.length ? `<div style="display:flex;gap:18px;margin-bottom:14px;">${checkboxes.join('')}</div>` : '');
}

// ── Edge helpers ──────────────────────────────────────────────────────────────

function addNetworkRow() {
  initializers['network.csv'].rows.push({ from: '', to: '', weight: '' });
  renderMain(); renderInitNav();
  setTimeout(() => { _setupResizeHandle(); drawNetPreview(); initNetVirtScroll(); }, 60);
}

function clearNetRows() {
  const rows = initializers['network.csv'].rows;
  if (!rows.length || !confirm(`Delete all ${rows.length} edges?`)) return;
  initializers['network.csv'].rows = [];
  renderMain(); renderInitNav();
  setTimeout(() => { _setupResizeHandle(); drawNetPreview(); initNetVirtScroll(); }, 60);
}

function sortEdgesAlpha() {
  initializers['network.csv'].rows.sort((a, b) => (a.from + a.to).localeCompare(b.from + b.to));
  renderMain();
  setTimeout(() => { _setupResizeHandle(); drawNetPreview(); initNetVirtScroll(); }, 60);
}

function generateTopology() {
  const agents = getAllAgentNames();
  if (!agents.length) { showToast('No agent instances. Add types with instances first.'); return; }
  const existing = initializers['network.csv'].rows.length;
  if (existing && !confirm(`Replace the existing ${existing} edges?`)) return;
  initializers['network.csv'].rows = generateEdges(agents);
  netView.positions = null;
  renderInitNav(); renderMain();
  setTimeout(() => { _setupResizeHandle(); netResetView(); drawNetPreview(); initNetVirtScroll(); }, 80);
}

// ── Resize handle ─────────────────────────────────────────────────────────────

function _setupResizeHandle() {
  const handle = $('#net-resize-handle');
  if (!handle || handle._resizeAttached) return;
  handle._resizeAttached = true;

  const startResize = (clientY) => {
    _resizing = true; _resizeStartY = clientY; _resizeStartH = netPreviewHeight;
  };
  const doResize = (clientY) => {
    if (!_resizing) return;
    netPreviewHeight = Math.max(120, _resizeStartH + (clientY - _resizeStartY));
    const body = $('#net-preview-body');
    if (body) body.style.height = netPreviewHeight + 'px';
    drawNetPreview();
  };
  const endResize = () => { _resizing = false; document.body.style.userSelect = ''; document.body.style.cursor = ''; };

  handle.addEventListener('mousedown', e => { startResize(e.clientY); document.body.style.userSelect = 'none'; document.body.style.cursor = 'ns-resize'; e.preventDefault(); });
  window.addEventListener('mousemove', e => doResize(e.clientY));
  window.addEventListener('mouseup',  endResize);

  handle.addEventListener('touchstart', e => { startResize(e.touches[0].clientY); e.preventDefault(); }, { passive: false });
  window.addEventListener('touchmove',  e => { if (_resizing) doResize(e.touches[0].clientY); });
  window.addEventListener('touchend',   endResize);
}

// ── View controls ─────────────────────────────────────────────────────────────

function netZoom(delta) {
  netView.scale = Math.min(8, Math.max(0.1, netView.scale + delta));
  drawNetPreview();
}

function netResetView() {
  netView.scale = 1; netView.offsetX = 0; netView.offsetY = 0;
  drawNetPreview();
}

// ── Canvas interaction ────────────────────────────────────────────────────────

function _setupCanvasInteraction(canvas) {
  if (canvas._netInteractive) return;
  canvas._netInteractive = true;

  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const delta = e.deltaY < 0 ? 0.15 : -0.15;
    const old   = netView.scale;
    netView.scale = Math.min(8, Math.max(0.1, old + delta));
    netView.offsetX -= (e.clientX - rect.left) * (netView.scale - old);
    netView.offsetY -= (e.clientY - rect.top)  * (netView.scale - old);
    drawNetPreview();
  }, { passive: false });

  canvas.addEventListener('mousedown', e => {
    netView.dragging = true; netView.lastX = e.clientX; netView.lastY = e.clientY;
    canvas.style.cursor = 'grabbing';
  });
  window.addEventListener('mousemove', e => {
    if (!netView.dragging) return;
    netView.offsetX += e.clientX - netView.lastX; netView.lastX = e.clientX;
    netView.offsetY += e.clientY - netView.lastY; netView.lastY = e.clientY;
    drawNetPreview();
  });
  window.addEventListener('mouseup', () => {
    if (netView.dragging) { netView.dragging = false; const c = $('#net-canvas'); if (c) c.style.cursor = 'grab'; }
  });

  let lastTouchDist = null;
  canvas.addEventListener('touchstart', e => {
    if (e.touches.length === 1) { netView.dragging = true; netView.lastX = e.touches[0].clientX; netView.lastY = e.touches[0].clientY; }
    if (e.touches.length === 2) { netView.dragging = false; lastTouchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY); }
  }, { passive: true });

  canvas.addEventListener('touchmove', e => {
    e.preventDefault();
    if (e.touches.length === 1 && netView.dragging) {
      netView.offsetX += e.touches[0].clientX - netView.lastX; netView.lastX = e.touches[0].clientX;
      netView.offsetY += e.touches[0].clientY - netView.lastY; netView.lastY = e.touches[0].clientY;
      drawNetPreview();
    }
    if (e.touches.length === 2 && lastTouchDist !== null) {
      const dist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      netView.scale = Math.min(8, Math.max(0.1, netView.scale * (dist / lastTouchDist)));
      lastTouchDist = dist; drawNetPreview();
    }
  }, { passive: false });
  canvas.addEventListener('touchend', () => { netView.dragging = false; lastTouchDist = null; });
}

// ── Draw (RAF-throttled) ──────────────────────────────────────────────────────

const MAX_DRAW_EDGES = 4000;
const MAX_DRAW_NODES = 2000;
let _rafPending = false;

function drawNetPreview() {
  if (_rafPending) return;
  _rafPending = true;
  requestAnimationFrame(_drawFrame);
}

function _drawFrame() {
  _rafPending = false;
  const canvas = $('#net-canvas'); if (!canvas) return;

  _setupCanvasInteraction(canvas);
  canvas.style.cursor = netView.dragging ? 'grabbing' : 'grab';

  const dpr = window.devicePixelRatio || 1;
  const W   = canvas.offsetWidth  || canvas.parentElement?.offsetWidth  || 400;
  const H   = canvas.offsetHeight || canvas.parentElement?.offsetHeight || netPreviewHeight;
  canvas.width  = W * dpr; canvas.height = H * dpr;

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.fillStyle = '#0a0c10'; ctx.fillRect(0, 0, W, H);

  const st     = initializers['network.csv'];
  const known  = new Set(getAllAgentNames());
  const nodeSet = new Set([...known]);
  for (const r of st.rows) { if (r.from) nodeSet.add(r.from); if (r.to) nodeSet.add(r.to); }
  const nodes = [...nodeSet];

  if (!nodes.length) {
    ctx.fillStyle = '#7a82a0'; ctx.font = '12px DM Sans,sans-serif';
    ctx.textAlign = 'center'; ctx.fillText('No nodes yet', W / 2, H / 2);
    const stats = $('#net-preview-stats'); if (stats) stats.textContent = '';
    return;
  }

  // Build / reuse circular layout
  const key = `${nodes.length}|${nodes[0]}|${nodes.at(-1)}`;
  if (!netView.positions || netView.positions._key !== key) {
    const margin = 48, step = (2 * Math.PI) / nodes.length;
    const pos = { _key: key };
    nodes.forEach((n, i) => {
      const a = -Math.PI / 2 + i * step;
      pos[n] = { x: W / 2 + (W / 2 - margin) * Math.cos(a), y: H / 2 + (H / 2 - margin) * Math.sin(a) };
    });
    netView.positions = pos;
  }
  const pos = netView.positions;

  ctx.save();
  ctx.translate(netView.offsetX, netView.offsetY);
  ctx.scale(netView.scale, netView.scale);

  // Edges
  const edgeStep = Math.max(1, Math.ceil(st.rows.length / MAX_DRAW_EDGES));
  ctx.beginPath(); ctx.strokeStyle = 'rgba(91,141,246,0.30)'; ctx.lineWidth = 1 / netView.scale;
  for (let i = 0; i < st.rows.length; i += edgeStep) {
    const r = st.rows[i];
    if (!r.from || !r.to || !pos[r.from] || !pos[r.to]) continue;
    ctx.moveTo(pos[r.from].x, pos[r.from].y);
    ctx.lineTo(pos[r.to].x,   pos[r.to].y);
  }
  ctx.stroke();

  // Arrows (for small graphs)
  if (nodes.length <= 80) {
    ctx.fillStyle = 'rgba(91,141,246,0.45)'; ctx.beginPath();
    for (let i = 0; i < st.rows.length; i += edgeStep) {
      const r = st.rows[i];
      if (!r.from || !r.to || !pos[r.from] || !pos[r.to]) continue;
      const { x: x1, y: y1 } = pos[r.from], { x: x2, y: y2 } = pos[r.to];
      const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy); if (len < 1) continue;
      const ux = dx / len, uy = dy / len;
      const ax = x2 - ux * 6, ay = y2 - uy * 6;
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - ux * 6 + uy * 3, ay - uy * 6 - ux * 3);
      ctx.lineTo(ax - ux * 6 - uy * 3, ay - uy * 6 + ux * 3);
      ctx.closePath();
    }
    ctx.fill();
  }

  // Nodes
  const nodeR     = nodes.length > 500 ? 2 : Math.max(3, Math.min(9, 140 / nodes.length));
  const nodeStep  = Math.max(1, Math.ceil(nodes.length / MAX_DRAW_NODES));
  const showLabel = nodes.length <= 40;

  for (const [fill, filter] of [
    ['rgba(61,255,208,0.85)', n => known.has(n)],
    ['rgba(91,141,246,0.6)',  n => !known.has(n)],
  ]) {
    ctx.fillStyle = fill; ctx.beginPath();
    for (let i = 0; i < nodes.length; i += nodeStep) {
      const n = nodes[i]; if (!filter(n) || !pos[n]) continue;
      ctx.moveTo(pos[n].x + nodeR, pos[n].y); ctx.arc(pos[n].x, pos[n].y, nodeR, 0, Math.PI * 2);
    }
    ctx.fill();
  }

  if (nodes.length <= 300) {
    ctx.lineWidth = 1 / netView.scale;
    for (let i = 0; i < nodes.length; i += nodeStep) {
      const n = nodes[i]; if (!pos[n]) continue;
      ctx.beginPath(); ctx.arc(pos[n].x, pos[n].y, nodeR, 0, Math.PI * 2);
      ctx.strokeStyle = known.has(n) ? 'rgba(61,255,208,0.35)' : 'rgba(91,141,246,0.25)';
      ctx.stroke();
    }
  }

  if (showLabel) {
    ctx.fillStyle = '#e8ecf5'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = `${Math.max(8, Math.min(11, 100 / nodes.length)) / netView.scale}px Space Mono,monospace`;
    for (const n of nodes) {
      if (!pos[n]) continue;
      const labelR = nodeR + 8 / netView.scale;
      const angle  = Math.atan2(pos[n].y - H / 2, pos[n].x - W / 2);
      ctx.fillText(n.length > 10 ? n.slice(0, 9) + '…' : n,
        pos[n].x + Math.cos(angle) * labelR, pos[n].y + Math.sin(angle) * labelR);
    }
  }

  ctx.restore();

  const stats = $('#net-preview-stats');
  if (stats) {
    const sampled = edgeStep > 1 ? ` · showing 1 in ${edgeStep} edges` : '';
    stats.textContent = `${nodes.length} nodes · ${st.rows.length} edges · ${Math.round(netView.scale * 100)}%${sampled}`;
  }
}

// ── Edge generation ───────────────────────────────────────────────────────────

function randWeight() {
  const { weight_min: mn, weight_max: mx } = topoParams;
  return mn === mx ? mn : +((Math.random() * (mx - mn) + mn).toFixed(3));
}

function makeEdge(from, to) {
  const w = randWeight();
  return { from, to, weight: (topoParams.weight_min === 1 && topoParams.weight_max === 1) ? '' : String(w) };
}

function generateEdges(agents) {
  const n = agents.length; if (!n) return [];
  const edges = [], seen = new Set();

  const add = (a, b) => {
    const key = topoParams.directed ? `${a}|${b}` : [a, b].sort().join('|');
    if (!seen.has(key)) { seen.add(key); edges.push(makeEdge(agents[a], agents[b])); }
  };

  switch (selectedTopo) {
    case 'random':
      for (let i = 0; i < n; i++)
        for (let j = topoParams.directed ? 0 : i + 1; j < n; j++) {
          if (i === j && !topoParams.self_loops) continue;
          if (Math.random() < topoParams.p) add(i, j);
          if (topoParams.directed && i !== j && Math.random() < topoParams.p) add(j, i);
        }
      break;

    case 'small_world': {
      const k = Math.max(1, Math.floor(topoParams.k / 2));
      for (let i = 0; i < n; i++) for (let d = 1; d <= k; d++) { add(i, (i + d) % n); if (topoParams.directed) add((i + d) % n, i); }
      const base = [...edges]; edges.length = 0; seen.clear();
      for (const e of base) {
        let a = agents.indexOf(e.from), b = agents.indexOf(e.to);
        if (Math.random() < topoParams.p) {
          let nb, t = 0;
          do { nb = Math.floor(Math.random() * n); t++; } while ((nb === a || seen.has(`${a}|${nb}`)) && t < 50);
          if (t < 50) b = nb;
        }
        add(a, b);
      }
      break;
    }

    case 'scale_free': {
      const m = Math.max(1, Math.min(topoParams.m, n - 1));
      const deg = new Array(n).fill(0);
      for (let i = 0; i < m; i++) for (let j = i + 1; j < m; j++) { add(i, j); deg[i]++; deg[j]++; }
      for (let i = m; i < n; i++) {
        const targets = new Set();
        while (targets.size < m) {
          const total = deg.reduce((s, d) => s + d, 0) || 1;
          let r = Math.random() * total, acc = 0;
          for (let j = 0; j < i; j++) { acc += deg[j]; if (acc >= r) { targets.add(j); break; } }
        }
        for (const t of targets) { add(t, i); deg[t]++; deg[i]++; }
      }
      if (topoParams.directed) [...edges].forEach(e => add(agents.indexOf(e.to), agents.indexOf(e.from)));
      break;
    }

    case 'ring': {
      const k = Math.max(1, Math.floor(topoParams.k / 2));
      for (let i = 0; i < n; i++) for (let d = 1; d <= k; d++) { add(i, (i + d) % n); if (topoParams.directed) add((i + d) % n, i); }
      break;
    }

    case 'complete':
      for (let i = 0; i < n; i++) for (let j = topoParams.directed ? 0 : i + 1; j < n; j++) {
        if (i === j && !topoParams.self_loops) continue; add(i, j);
      }
      break;

    case 'star': {
      const hub = Math.floor(Math.random() * n);
      for (let i = 0; i < n; i++) if (i !== hub) { add(hub, i); if (topoParams.directed) add(i, hub); }
      break;
    }

    case 'bipartite': {
      const half = Math.floor(n / 2);
      for (let i = 0; i < half; i++) for (let j = half; j < n; j++)
        if (Math.random() < topoParams.p) { add(i, j); if (topoParams.directed) add(j, i); }
      break;
    }
  }

  if (!topoParams.directed) {
    const ex = new Set(edges.map(e => `${e.from}|${e.to}`));
    edges.push(...edges.filter(e => !ex.has(`${e.to}|${e.from}`)).map(e => makeEdge(e.to, e.from)));
  }
  return edges;
}
