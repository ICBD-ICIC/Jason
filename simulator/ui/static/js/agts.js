// agts.js — agent metrics charts
// Requires: utils.js (for esc)
// Expects globals: AGENTS_DATA, FOLDER (injected by server template)

const PALETTE = [
  '#f0c040','#4dd4b0','#cc66cc','#6699ee',
  '#ee8855','#88dd55','#ee6699','#55dddd',
  '#c4a05b','#a05bc4','#5bc4c4','#c45b5b',
];

const agentNames  = Object.keys(AGENTS_DATA);
const agentColors = Object.fromEntries(agentNames.map((a, i) => [a, PALETTE[i % PALETTE.length]]));

// ── Variable metadata ─────────────────────────────────────────────────────────
function inferType(vals) {
  const nn = vals.filter(v => v !== null && v !== undefined && v !== '');
  if (!nn.length) return 'unknown';
  return nn.every(v => typeof v === 'number' || (typeof v === 'string' && !isNaN(+v))) ? 'numeric' : 'categorical';
}

const varMeta = {};
for (const rows of Object.values(AGENTS_DATA))
  for (const row of rows)
    for (const [k, v] of Object.entries(row)) {
      if (k === 'timestamp') continue;
      (varMeta[k] = varMeta[k] || { values: [] }).values.push(v);
    }
for (const [k, m] of Object.entries(varMeta)) { m.type = inferType(m.values); delete m.values; }
const varNames = Object.keys(varMeta).sort();

// ── App state ─────────────────────────────────────────────────────────────────
let activeAgents = new Set(agentNames);
let activeVars   = new Set();
let plotType     = 'line';
const chartInsts = {};

const PLOT_TYPES = [
  { id: 'line',    icon: '⟋', label: 'Line (time series)' },
  { id: 'bar',     icon: '▋', label: 'Bar chart'          },
  { id: 'step',    icon: '⌐', label: 'Step line'          },
  { id: 'scatter', icon: '·', label: 'Scatter'            },
  { id: 'dist',    icon: '⌇', label: 'Distribution'       },
];

// ── Sidebar ───────────────────────────────────────────────────────────────────
function buildSidebar() {
  document.getElementById('plot-types').innerHTML = PLOT_TYPES.map(p => `
    <button class="pt-btn ${p.id===plotType?'active':''}" onclick="setPlotType('${p.id}')">
      <span class="pt-icon">${p.icon}</span>${p.label}
    </button>`).join('');

  document.getElementById('agent-list').innerHTML = agentNames.map(a => `
    <div class="agent-item ${activeAgents.has(a)?'active':''}"
         style="--agent-color:${agentColors[a]}"
         onclick="toggleAgent('${a.replace(/'/g,"\\'")}')">
      <span class="agent-dot" style="background:${agentColors[a]}"></span>
      <span class="agent-name">${esc(a)}</span>
      <span class="agent-count">${(AGENTS_DATA[a]||[]).length}</span>
      <span class="agent-check">
        <svg width="9" height="9" viewBox="0 0 10 10" fill="none" stroke="white" stroke-width="2">
          <polyline points="1.5,5.5 4,8 8.5,2"/>
        </svg>
      </span>
    </div>`).join('') || '<div style="padding:6px 16px;font-size:.8rem;color:var(--muted)">No agents</div>';

  document.getElementById('var-list').innerHTML = varNames.map(v => `
    <div class="var-item ${activeVars.has(v)?'active':''}" onclick="toggleVar('${v.replace(/'/g,"\\'")}')">
      <span class="var-pill" style="background:${activeVars.has(v)?'var(--accent)':'var(--dim)'}"></span>
      <span class="var-name">${esc(v)}</span>
      <span class="var-type">${varMeta[v]?.type||''}</span>
    </div>`).join('') || '<div style="padding:6px 16px;font-size:.8rem;color:var(--muted)">No variables</div>';
}

// ── Actions ───────────────────────────────────────────────────────────────────
function setPlotType(pt) { plotType = pt; buildSidebar(); renderCharts(); }
function toggleAgent(a)  { activeAgents.has(a) ? activeAgents.delete(a) : activeAgents.add(a); buildSidebar(); renderCharts(); }
function toggleVar(v)    { activeVars.has(v)   ? activeVars.delete(v)   : activeVars.add(v);   buildSidebar(); renderCharts(); }
function removeVar(v)    { activeVars.delete(v); buildSidebar(); renderCharts(); }
function resetAll()      { activeAgents = new Set(agentNames); activeVars = new Set(); plotType = 'line'; buildSidebar(); renderCharts(); }

// ── Data helpers ──────────────────────────────────────────────────────────────
function getValues(agent, varName) {
  return (AGENTS_DATA[agent]||[]).map(r => {
    const v = r[varName];
    if (v === undefined || v === null || v === '') return null;
    const n = +v; return isNaN(n) ? v : n;
  });
}
const getTimestamps = agent => (AGENTS_DATA[agent]||[]).map(r => r.timestamp || 0);

// ── Charts ────────────────────────────────────────────────────────────────────
const GRID = '#252e42', TICK = '#8899bb', FONT = { family: 'IBM Plex Mono', size: 11 };
const baseScales = {
  x: { ticks: { color: TICK, font: FONT, maxTicksLimit: 7 }, grid: { color: GRID } },
  y: { ticks: { color: TICK, font: FONT }, grid: { color: GRID } },
};

function renderCharts() {
  const grid = document.getElementById('chart-grid');

  // Destroy charts for removed vars
  for (const [v, inst] of Object.entries(chartInsts)) {
    if (!activeVars.has(v)) { inst.destroy(); delete chartInsts[v]; }
  }

  if (!activeVars.size) {
    grid.innerHTML = `
      <div class="placeholder">
        <div class="placeholder-icon">⬡</div>
        <div class="placeholder-msg">No variables selected.</div>
        <div class="placeholder-hint">Pick variables from the sidebar to plot them.</div>
      </div>`;
    updateStats(); return;
  }

  // Remove cards for removed vars
  for (const card of [...grid.querySelectorAll('.chart-card')])
    if (!activeVars.has(card.dataset.varid)) card.remove();

  // Add cards for new vars
  for (const v of activeVars) {
    const safeId = CSS.escape(v);
    if (!document.getElementById(`chart-card-${safeId}`)) {
      const card = document.createElement('div');
      card.className     = 'chart-card';
      card.id            = `chart-card-${safeId}`;
      card.dataset.varid = v;
      card.innerHTML = `
        <div class="chart-header">
          <span class="chart-var-name">${esc(v)}</span>
          <span class="chart-badge">${varMeta[v]?.type||''}</span>
          <div class="chart-spacer"></div>
          <button class="chart-remove" title="Remove" onclick="removeVar(${JSON.stringify(v)})">✕</button>
        </div>
        <div class="chart-body"><canvas id="canvas-${safeId}"></canvas></div>
        <div class="chart-legend" id="legend-${safeId}"></div>`;
      grid.appendChild(card);
    }
    updateChart(v);
  }
  updateStats();
}

function updateChart(varName) {
  const safeId = CSS.escape(varName);
  const canvas = document.getElementById(`canvas-${safeId}`); if (!canvas) return;
  if (chartInsts[varName]) { chartInsts[varName].destroy(); delete chartInsts[varName]; }

  const type   = varMeta[varName]?.type || 'numeric';
  const agents = [...activeAgents].filter(a => AGENTS_DATA[a]);
  let config;

  if (plotType === 'dist') {
    const allNums = agents.flatMap(a => getValues(a, varName).filter(v => typeof v === 'number'));
    const bins    = 20;
    const [gMin, gMax] = allNums.length ? [Math.min(...allNums), Math.max(...allNums)] : [0, 1];
    const step    = (gMax - gMin) / bins || 1;
    const labels  = Array.from({ length: bins }, (_, i) => (gMin + i*step).toFixed(2));
    config = {
      type: 'bar',
      data: { labels, datasets: agents.map(a => {
        const counts = Array(bins).fill(0);
        for (const n of getValues(a, varName).filter(v => typeof v === 'number'))
          counts[Math.min(Math.floor((n - gMin) / step), bins-1)]++;
        return { label: a, data: counts, backgroundColor: agentColors[a]+'99', borderColor: agentColors[a], borderWidth: 1 };
      })},
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: baseScales },
    };
  } else if (type === 'categorical' || plotType === 'bar') {
    const allVals  = agents.flatMap(a => getValues(a, varName).filter(v => v !== null));
    const distinct = [...new Set(allVals)].sort();
    config = {
      type: 'bar',
      data: { labels: distinct.map(String), datasets: agents.map(a => {
        const vals = getValues(a, varName);
        return { label: a, data: distinct.map(d => vals.filter(v => v===d).length), backgroundColor: agentColors[a]+'99', borderColor: agentColors[a], borderWidth: 1 };
      })},
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: baseScales },
    };
  } else {
    config = {
      type: 'line',
      data: { datasets: agents.map(a => {
        const pts = getTimestamps(a).map((t, i) => ({ x: t, y: getValues(a, varName)[i] })).filter(p => p.y !== null);
        return {
          label: a, data: pts,
          borderColor: agentColors[a], backgroundColor: agentColors[a]+'22',
          pointRadius: pts.length < 80 ? 3 : 0, pointHoverRadius: 5, borderWidth: 2,
          tension: plotType === 'line' ? 0.35 : 0,
          stepped: plotType === 'step' ? 'before' : false,
          showLine: plotType !== 'scatter',
        };
      })},
      options: {
        responsive: true, maintainAspectRatio: false, parsing: false,
        plugins: { legend: { display: false } },
        scales: { ...baseScales, x: { type: 'linear', ticks: { color: TICK, font: FONT, maxTicksLimit: 6,
          callback: v => fmtTime(v),
        }, grid: { color: GRID } } },
      },
    };
  }

  chartInsts[varName] = new Chart(canvas, config);

  const legendEl = document.getElementById(`legend-${safeId}`);
  if (legendEl) legendEl.innerHTML = agents.map(a =>
    `<span class="leg-item"><span class="leg-swatch" style="background:${agentColors[a]}"></span>${esc(a)}</span>`
  ).join('');
}

function updateStats() {
  const totalRows = agentNames.reduce((s, a) => s + (AGENTS_DATA[a]||[]).length, 0);
  document.getElementById('stats-bar').innerHTML = `
    <span class="stat-item"><span class="stat-val">${agentNames.length}</span>&nbsp;agents</span>
    <span class="stat-item"><span class="stat-val">${varNames.length}</span>&nbsp;variables</span>
    <span class="stat-item"><span class="stat-val">${totalRows}</span>&nbsp;log entries</span>
    <span class="stat-item"><span class="stat-val">${activeVars.size}</span>&nbsp;charts active</span>`;
  document.getElementById('hdr-count').textContent = `${[...activeAgents].length} / ${agentNames.length} agents`;
}

// ── Chart.js defaults + boot ──────────────────────────────────────────────────
Chart.defaults.color       = '#8899bb';
Chart.defaults.borderColor = '#252e42';
Chart.defaults.font.family = 'IBM Plex Mono';

buildSidebar();
renderCharts();
