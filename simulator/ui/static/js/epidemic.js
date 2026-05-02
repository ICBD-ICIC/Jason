// epidemic.js — Agent state epidemiological dashboard
// Expects globals: AGENTS_DATA, FOLDER, NETWORK_DATA (injected by server template)

// ── Constants ─────────────────────────────────────────────────────────────────
const STATES      = ['neutral', 'vaccinated', 'infected'];
const STATE_COLOR = { neutral: '#3a4055', vaccinated: '#2de89a', infected: '#f5604a' };
const STATE_LABEL = { neutral: 'Neutral', vaccinated: 'Vaccinated', infected: 'Infected' };

// State index for canvas rendering
const STATE_IDX = { neutral: 0, vaccinated: 1, infected: 2 };

// ── Parse agent timelines ─────────────────────────────────────────────────────
const agentNames = Object.keys(AGENTS_DATA);
const N = agentNames.length;

// Build sorted transition list per agent — same as before
const agentTimelines = {};
for (const name of agentNames) {
  const rows = AGENTS_DATA[name] || [];
  const transitions = [];
  for (const row of rows) {
    if (row.state && row.timestamp != null) {
      transitions.push({ timestamp: row.timestamp, state: row.state });
    }
  }
  transitions.sort((a, b) => a.timestamp - b.timestamp);
  agentTimelines[name] = transitions;
}

const allTimestamps = new Set();
for (const name of agentNames) {
  for (const row of AGENTS_DATA[name] || []) {
    if (row.timestamp != null) allTimestamps.add(row.timestamp);
  }
}
const sortedTimestamps = [...allTimestamps].sort((a, b) => a - b);

const MAX_STEPS = 300;
function subsample(arr, maxN) {
  if (arr.length <= maxN) return arr;
  const step = arr.length / maxN;
  return Array.from({ length: maxN }, (_, i) => arr[Math.floor(i * step)]);
}
const steps = subsample(sortedTimestamps, MAX_STEPS);
const tMin = steps[0] ?? 0;
const tMax = steps[steps.length - 1] ?? 1;

// ── PERF: Binary-search getStateAt instead of linear scan ────────────────────
function getStateAt(name, ts) {
  const tl = agentTimelines[name];
  if (!tl || !tl.length) return 'neutral';
  // Binary search for last entry with timestamp <= ts
  let lo = 0, hi = tl.length - 1, result = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1;
    if (tl[mid].timestamp <= ts) { result = mid; lo = mid + 1; }
    else hi = mid - 1;
  }
  return result === -1 ? 'neutral' : tl[result].state;
}

// ── PERF: Pre-build per-agent state snapshots for all steps ──────────────────
// agentStepStates[agentIdx][stepIdx] = state string
// This turns repeated getStateAt calls during playback into O(1) lookups.
const agentStepStates = new Array(N);
for (let ai = 0; ai < N; ai++) {
  const name = agentNames[ai];
  const tl   = agentTimelines[name];
  const snap = new Array(steps.length);
  let tlIdx  = -1;          // last tl entry applied
  let cur    = 'neutral';
  let nextTlIdx = 0;

  for (let si = 0; si < steps.length; si++) {
    const ts = steps[si];
    // Advance timeline pointer while next entry is still <= ts
    while (nextTlIdx < tl.length && tl[nextTlIdx].timestamp <= ts) {
      cur = tl[nextTlIdx].state;
      nextTlIdx++;
    }
    snap[si] = cur;
  }
  agentStepStates[ai] = snap;
}

// Fast lookup — replaces getStateAt for known step indices
function getStateAtStep(agentIdx, stepIdx) {
  return agentStepStates[agentIdx][stepIdx];
}

// ── Precompute state counts using snapshot array ──────────────────────────────
const stateCounts = steps.map((_, si) => {
  const counts = { neutral: 0, vaccinated: 0, infected: 0 };
  for (let ai = 0; ai < N; ai++) {
    const s = agentStepStates[ai][si];
    counts[s] = (counts[s] || 0) + 1;
  }
  return counts;
});

// ── App state ─────────────────────────────────────────────────────────────────
let currentStep = steps.length - 1;
let playing = false;
let playTimer = null;
let playSpeed = 200;

// ── Boot ──────────────────────────────────────────────────────────────────────
Chart.defaults.color = '#8899bb';
Chart.defaults.borderColor = '#252e42';
Chart.defaults.font.family = 'Space Mono, monospace';

let stackedChart = null;
let pieChart = null;
let growthChart = null;

function init() {
  renderStats();
  buildStateCards();
  buildTimelineChart();
  buildPieChart();
  buildGrowthChart();
  buildTransitionsTable();
  buildAgentDotGrid();   // now canvas-based
  buildScrubber();
  initNetworkGraph();
  updateToStep(steps.length - 1);
}

// ── Stats bar ─────────────────────────────────────────────────────────────────
function renderStats() {
  document.getElementById('stats-bar').innerHTML = `
    <span class="stat-item"><span class="stat-val">${N}</span>&nbsp;agents</span>
    <span class="stat-item"><span class="stat-val">${steps.length}</span>&nbsp;time steps</span>
    <span class="stat-item"><span class="stat-val">${fmtDateTime(tMin)}</span>&nbsp;start</span>
    <span class="stat-item"><span class="stat-val">${fmtDateTime(tMax)}</span>&nbsp;end</span>
  `;
  document.getElementById('hdr-count').textContent = `${N} agents`;
}

// ── State cards (sidebar) ─────────────────────────────────────────────────────
function buildStateCards() {
  document.getElementById('state-cards').innerHTML = STATES.map(s => `
    <div class="state-card ${s}">
      <div class="state-card-dot" style="background:${STATE_COLOR[s]}"></div>
      <div class="state-card-info">
        <div class="state-card-name">${STATE_LABEL[s]}</div>
        <div class="state-card-count" id="card-count-${s}">—</div>
        <div class="state-card-pct" id="card-pct-${s}">— %</div>
      </div>
    </div>`).join('');
}

function updateStateCards(counts) {
  for (const s of STATES) {
    const v = counts[s] || 0;
    document.getElementById(`card-count-${s}`).textContent = v.toLocaleString();
    document.getElementById(`card-pct-${s}`).textContent = ((v / N) * 100).toFixed(1) + '%';
  }
}

// ── Stacked area chart ────────────────────────────────────────────────────────
function buildTimelineChart() {
  const canvas = document.getElementById('stacked-canvas');
  if (!canvas) return;

  const labels = steps.map(ts => fmtDateTime(ts));
  const datasets = STATES.map(s => ({
    label: STATE_LABEL[s],
    data: stateCounts.map(c => c[s] || 0),
    backgroundColor: STATE_COLOR[s] + (s === 'neutral' ? '88' : 'cc'),
    borderColor: STATE_COLOR[s],
    borderWidth: 1.5,
    fill: true,
    tension: 0.3,
    pointRadius: 0,
  }));

  stackedChart = new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2030',
          borderColor: '#2a3045',
          borderWidth: 1,
          titleColor: '#e8ecf5',
          bodyColor: '#8899bb',
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.raw} (${((ctx.raw / N) * 100).toFixed(1)}%)`,
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          ticks: { color: '#7a82a0', font: { size: 10, family: 'Space Mono' }, maxTicksLimit: 8, maxRotation: 0 },
          grid: { color: '#1b2235' },
        },
        y: {
          stacked: true,
          min: 0, max: N,
          ticks: { color: '#7a82a0', font: { size: 10, family: 'Space Mono' } },
          grid: { color: '#1b2235' },
        },
      },
      animation: { duration: 0 },
      onClick: (e, elements, chart) => {
        if (elements.length) updateToStep(elements[0].index);
      },
    },
  });
}

// ── Pie / donut chart ─────────────────────────────────────────────────────────
function buildPieChart() {
  const canvas = document.getElementById('pie-canvas');
  if (!canvas) return;

  pieChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: STATES.map(s => STATE_LABEL[s]),
      datasets: [{
        data: STATES.map(s => stateCounts[currentStep]?.[s] || 0),
        backgroundColor: STATES.map(s => STATE_COLOR[s] + 'cc'),
        borderColor: STATES.map(s => STATE_COLOR[s]),
        borderWidth: 2,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2030',
          borderColor: '#2a3045',
          borderWidth: 1,
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.raw} (${((ctx.raw / N) * 100).toFixed(1)}%)`,
          },
        },
      },
      animation: { duration: 150 },
    },
  });
}

function updatePieChart(counts) {
  if (!pieChart) return;
  pieChart.data.datasets[0].data = STATES.map(s => counts[s] || 0);
  pieChart.update();
}

// ── Daily growth / rate chart ─────────────────────────────────────────────────
function buildGrowthChart() {
  const canvas = document.getElementById('growth-canvas');
  if (!canvas) return;

  const newInfected = stateCounts.map((c, i) => {
    if (i === 0) return 0;
    return Math.max(0, c.infected - stateCounts[i - 1].infected);
  });
  const newVacc = stateCounts.map((c, i) => {
    if (i === 0) return 0;
    return Math.max(0, c.vaccinated - stateCounts[i - 1].vaccinated);
  });

  growthChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: steps.map(ts => fmtDateTime(ts)),
      datasets: [
        {
          label: 'New infected',
          data: newInfected,
          backgroundColor: '#f5604a88',
          borderColor: '#f5604a',
          borderWidth: 1,
          order: 2,
        },
        {
          label: 'New vaccinated',
          data: newVacc,
          backgroundColor: '#2de89a66',
          borderColor: '#2de89a',
          borderWidth: 1,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2030',
          borderColor: '#2a3045',
          borderWidth: 1,
          bodyColor: '#8899bb',
        },
      },
      scales: {
        x: {
          ticks: { color: '#7a82a0', font: { size: 10, family: 'Space Mono' }, maxTicksLimit: 8, maxRotation: 0 },
          grid: { color: '#1b2235' },
        },
        y: {
          ticks: { color: '#7a82a0', font: { size: 10, family: 'Space Mono' } },
          grid: { color: '#1b2235' },
        },
      },
      animation: { duration: 0 },
    },
  });
}

// ── Transition table ──────────────────────────────────────────────────────────
function buildTransitionsTable() {
  const trans = {};
  for (const name of agentNames) {
    const tl = agentTimelines[name];
    let prev = 'neutral';
    for (const { state } of tl) {
      if (state !== prev) {
        const key = `${prev}→${state}`;
        trans[key] = (trans[key] || 0) + 1;
        prev = state;
      }
    }
  }

  const sorted = Object.entries(trans).sort((a, b) => b[1] - a[1]);
  const maxCount = sorted[0]?.[1] || 1;
  const tbody = document.getElementById('trans-tbody');
  if (!tbody) return;

  if (!sorted.length) {
    tbody.innerHTML = `<tr><td colspan="2" style="padding:16px;color:var(--muted);font-size:.8rem;text-align:center">No state transitions found in logs.</td></tr>`;
    return;
  }

  tbody.innerHTML = sorted.map(([key, count]) => {
    const [from, to] = key.split('→');
    const pct = ((count / maxCount) * 100).toFixed(0);
    const barColor = STATE_COLOR[to] || '#5b8df6';
    return `<tr>
      <td>
        <span class="trans-from ${from}">${STATE_LABEL[from] || from}</span>
        <span class="trans-arrow">→</span>
        <span class="trans-to ${to}">${STATE_LABEL[to] || to}</span>
        <div class="trans-bar-wrap"><div class="trans-bar" style="width:${pct}%;background:${barColor}"></div></div>
      </td>
      <td><span class="trans-count">${count.toLocaleString()}</span></td>
    </tr>`;
  }).join('');
}

// ── PERF: Canvas-based agent dot grid ─────────────────────────────────────────
// Replaces 14k DOM elements with a single <canvas> draw call per step.

let dotCanvas = null;
let dotCtx    = null;
// Pre-parse colors once as RGB arrays for fast canvas fillStyle setting
const STATE_RGB = {
  neutral:    [58,  64,  85],
  vaccinated: [45, 232, 154],
  infected:   [245, 96,  74],
};

function buildAgentDotGrid() {
  const wrap = document.getElementById('agent-dot-grid');
  if (!wrap) return;

  // Replace the wrap contents with a canvas
  wrap.innerHTML = '';
  dotCanvas = document.createElement('canvas');
  dotCanvas.style.display = 'block';
  wrap.appendChild(dotCanvas);

  // Initial draw will happen via updateDotGrid
}

function updateDotGrid(stepIdx) {
  if (!dotCanvas) return;
  const wrap = dotCanvas.parentElement;
  if (!wrap) return;

  const DOT  = 9;   // dot width/height in px
  const GAP  = 3;   // gap between dots
  const CELL = DOT + GAP;

  const wrapW = wrap.clientWidth || 400;
  const cols  = Math.max(1, Math.floor((wrapW + GAP) / CELL));
  const rows  = Math.ceil(N / cols);

  const dpr = window.devicePixelRatio || 1;
  const cssW = cols * CELL - GAP;
  const cssH = rows * CELL - GAP;

  dotCanvas.style.width  = cssW + 'px';
  dotCanvas.style.height = cssH + 'px';
  dotCanvas.width        = Math.round(cssW * dpr);
  dotCanvas.height       = Math.round(cssH * dpr);

  const ctx = dotCanvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, cssW, cssH);

  // Draw all dots in one pass, batched by state color to minimize fillStyle changes
  // First pass: group agent indices by state at this step
  const groups = { neutral: [], vaccinated: [], infected: [] };
  for (let ai = 0; ai < N; ai++) {
    const s = agentStepStates[ai][stepIdx] || 'neutral';
    groups[s].push(ai);
  }

  for (const [state, indices] of Object.entries(groups)) {
    if (!indices.length) continue;
    const [r, g, b] = STATE_RGB[state];
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.beginPath();
    for (const ai of indices) {
      const col = ai % cols;
      const row = Math.floor(ai / cols);
      const x   = col * CELL;
      const y   = row * CELL;
      // Rounded rect (DOT×DOT, radius 2)
      ctx.roundRect(x, y, DOT, DOT, 2);
    }
    ctx.fill();
  }
}

// ── Computed metrics ──────────────────────────────────────────────────────────
function buildMetricsPanel(stepIdx) {
  const cur = stateCounts[stepIdx] || { neutral: 0, vaccinated: 0, infected: 0 };
  const inf = cur.infected;
  const vacc = cur.vaccinated;
  const neu = cur.neutral;

  const peak = Math.max(...stateCounts.map(c => c.infected));
  const peakStep = stateCounts.findIndex(c => c.infected === peak);
  const peakTime = steps[peakStep] ? fmtDateTime(steps[peakStep]) : '—';
  const attackRate = ((inf + vacc) / N * 100).toFixed(1);

  let growthRate = '—';
  if (stepIdx > 0) {
    const prev = stateCounts[stepIdx - 1].infected;
    if (prev > 0) growthRate = ((inf - prev) / prev * 100).toFixed(1) + '%';
    else if (inf > 0) growthRate = '+∞';
    else growthRate = '0%';
  }

  const container = document.getElementById('metrics-tiles');
  if (!container) return;

  container.innerHTML = [
    { label: 'Infected now',   val: inf.toLocaleString(),  sub: ((inf/N)*100).toFixed(1)+'% of pop', cls: inf > 0 ? 'neg' : 'neu' },
    { label: 'Vaccinated now', val: vacc.toLocaleString(), sub: ((vacc/N)*100).toFixed(1)+'% of pop', cls: vacc > 0 ? 'pos' : 'neu' },
    { label: 'Susceptible',    val: neu.toLocaleString(),  sub: ((neu/N)*100).toFixed(1)+'% of pop', cls: 'neu' },
    { label: 'Peak infections', val: peak.toLocaleString(), sub: peakTime, cls: 'neg' },
    { label: 'Attack rate',    val: attackRate+'%', sub: 'infected or vacc', cls: parseFloat(attackRate) > 50 ? 'neg' : parseFloat(attackRate) > 20 ? 'neu' : 'pos' },
    { label: 'Growth (Δ)',     val: growthRate, sub: 'vs prev step', cls: (growthRate.startsWith('+') || growthRate.startsWith('∞')) ? 'neg' : 'pos' },
  ].map(t => `
    <div class="metric-tile">
      <div class="metric-tile-label">${t.label}</div>
      <div class="metric-tile-val ${t.cls}">${t.val}</div>
      <div class="metric-tile-sub">${t.sub}</div>
    </div>`).join('');
}

// ── Scrubber ──────────────────────────────────────────────────────────────────
function buildScrubber() {
  const track = document.getElementById('scrub-track');
  if (!track) return;

  const move = (clientX) => {
    const rect = track.getBoundingClientRect();
    const f = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const idx = Math.round(f * (steps.length - 1));
    updateToStep(idx);
  };

  let dragging = false;
  track.addEventListener('mousedown', e => { dragging = true; move(e.clientX); });
  window.addEventListener('mousemove', e => { if (dragging) move(e.clientX); });
  window.addEventListener('mouseup', () => { dragging = false; });
  track.addEventListener('touchstart', e => { dragging = true; move(e.touches[0].clientX); }, { passive: true });
  window.addEventListener('touchmove', e => { if (dragging) move(e.touches[0].clientX); }, { passive: true });
  window.addEventListener('touchend', () => { dragging = false; });
}

function updateScrubber(idx) {
  const pct = steps.length > 1 ? (idx / (steps.length - 1)) * 100 : 0;
  const fill = document.getElementById('scrub-fill');
  const thumb = document.getElementById('scrub-thumb');
  const label = document.getElementById('scrub-current');
  if (fill)  fill.style.width = pct + '%';
  if (thumb) thumb.style.left = pct + '%';
  if (label && steps[idx]) label.textContent = fmtDateTime(steps[idx]);
}

function updateStepBadge(idx) {
  const el = document.getElementById('step-badge');
  if (el) el.textContent = `Step ${idx + 1} / ${steps.length}`;
}

// ── Master update ─────────────────────────────────────────────────────────────
function updateToStep(idx) {
  currentStep = Math.max(0, Math.min(steps.length - 1, idx));
  const ts = steps[currentStep];
  const counts = stateCounts[currentStep] || { neutral: 0, vaccinated: 0, infected: 0 };

  updateStateCards(counts);
  updatePieChart(counts);
  updateDotGrid(currentStep);   // pass step index, not timestamp
  updateScrubber(currentStep);
  updateStepBadge(currentStep);
  buildMetricsPanel(currentStep);
  updateNetworkGraph(ts);
}

// ── Playback ──────────────────────────────────────────────────────────────────
function togglePlay() {
  playing = !playing;
  const btn = document.getElementById('play-btn');
  if (btn) {
    btn.textContent = playing ? '⏸ Pause' : '▶ Play';
    btn.classList.toggle('playing', playing);
  }
  if (playing) {
    if (currentStep >= steps.length - 1) updateToStep(0);
    tick();
  } else {
    clearTimeout(playTimer);
  }
}

function tick() {
  if (!playing) return;
  const next = currentStep + 1;
  if (next >= steps.length) {
    playing = false;
    const btn = document.getElementById('play-btn');
    if (btn) { btn.textContent = '▶ Play'; btn.classList.remove('playing'); }
    return;
  }
  updateToStep(next);
  playTimer = setTimeout(tick, playSpeed);
}

function setSpeed(ms) {
  playSpeed = ms;
  document.querySelectorAll('.speed-btn').forEach(b => {
    b.classList.toggle('active', +b.dataset.speed === ms);
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDateTime(ms) {
  return new Date(ms).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

// ════════════════════════════════════════════════════════════════════════════════
// ── Network Graph (D3 force-directed) ────────────────────────────────────────
// ════════════════════════════════════════════════════════════════════════════════

let netSvg = null;
let netSim = null;
let netG   = null;
let netZoom = null;
let netNodes = [];
let netEdges = [];

let fullAdjacency = {};
let fullAdjacencyFollowers = {};

function initNetworkGraph() {
  const svgEl = document.getElementById('net-svg');
  const emptyEl = document.getElementById('net-empty');

  if (!NETWORK_DATA || !NETWORK_DATA.loaded) {
    if (emptyEl) {
      emptyEl.style.display = 'flex';
      emptyEl.textContent = NETWORK_DATA?.error
        ? `⚠ Could not load network.csv\n${NETWORK_DATA.error}`
        : '⚠ network.csv not found in initializer/';
    }
    return;
  }

  for (const { source, target } of NETWORK_DATA.edges) {
    const s = String(source), t = String(target);
    if (!fullAdjacency[s]) fullAdjacency[s] = new Set();
    fullAdjacency[s].add(t);
    if (!fullAdjacencyFollowers[t]) fullAdjacencyFollowers[t] = new Set();
    fullAdjacencyFollowers[t].add(s);
  }

  netSvg = d3.select(svgEl);
  netG   = netSvg.append('g').attr('class', 'net-root');

  netZoom = d3.zoom()
    .scaleExtent([0.1, 6])
    .on('zoom', e => netG.attr('transform', e.transform));
  netSvg.call(netZoom);

  const defs = netSvg.append('defs');
  ['infected', 'vaccinated', 'neutral'].forEach(state => {
    defs.append('marker')
        .attr('id', `arrow-${state}`)
        .attr('viewBox', '0 -4 8 8')
        .attr('refX', 18).attr('refY', 0)
        .attr('markerWidth', 5).attr('markerHeight', 5)
        .attr('orient', 'auto')
        .append('path')
          .attr('d', 'M0,-4L8,0L0,4')
          .attr('fill', STATE_COLOR[state])
          .attr('opacity', 0.6);
  });

  netG.append('g').attr('class', 'net-links');
  netG.append('g').attr('class', 'net-nodes');

  netSim = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(60).strength(0.4))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('collide', d3.forceCollide(14))
    .alphaDecay(0.04)
    .on('tick', netTick);

  document.getElementById('net-show-neutral').addEventListener('change', () => updateNetworkGraph(steps[currentStep]));
  document.getElementById('net-show-labels').addEventListener('change', () => {
    netG.selectAll('.net-label').style('display', document.getElementById('net-show-labels').checked ? null : 'none');
  });
  document.getElementById('net-freeze-layout').addEventListener('change', e => {
    if (e.target.checked) netSim.alphaTarget(0).stop();
    else netSim.alphaTarget(0.05).restart();
  });
}

function updateNetworkGraph(ts) {
  if (!netSim || !netSvg) return;

  const showNeutral = document.getElementById('net-show-neutral')?.checked ?? true;
  const showLabels  = document.getElementById('net-show-labels')?.checked ?? false;

  // Use binary-search getStateAt for network graph (arbitrary ts, not snapped to step)
  const stateMap = {};
  for (const name of agentNames) stateMap[name] = getStateAt(name, ts);

  const activeSet = new Set(agentNames.filter(n => stateMap[n] !== 'neutral'));

  const neighbourSet = new Set();
  if (showNeutral) {
    for (const active of activeSet) {
      for (const { source, target } of NETWORK_DATA.edges) {
        if (String(target) === active && !activeSet.has(String(source)))
          neighbourSet.add(String(source));
      }
    }
  }

  const visibleSet = new Set([...activeSet, ...neighbourSet]);

  const visibleEdges = NETWORK_DATA.edges.filter(({ source, target }) => {
    const s = String(source), t = String(target);
    return visibleSet.has(s) && activeSet.has(t);
  });

  const statEl = document.getElementById('net-stat');
  if (statEl) statEl.innerHTML = `<span>${visibleSet.size}</span> nodes · <span>${visibleEdges.length}</span> edges`;

  const emptyEl = document.getElementById('net-empty');
  if (!visibleSet.size) {
    if (emptyEl) { emptyEl.style.display = 'flex'; emptyEl.textContent = 'No infected or vaccinated agents at this step.'; }
    netG.select('.net-links').selectAll('*').remove();
    netG.select('.net-nodes').selectAll('*').remove();
    netSim.stop();
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';

  const oldNodeMap = new Map(netNodes.map(n => [n.id, n]));
  const newNodeData = [...visibleSet].map(id => {
    const old = oldNodeMap.get(id);
    return old
      ? { ...old, state: stateMap[id] || 'neutral', isNeighbour: neighbourSet.has(id) }
      : { id, state: stateMap[id] || 'neutral', isNeighbour: neighbourSet.has(id) };
  });
  netNodes = newNodeData;

  const nodeIds = new Set(netNodes.map(n => n.id));
  netEdges = visibleEdges
    .map(({ source, target }) => ({ source: String(source), target: String(target) }))
    .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));

  const linkSel = netG.select('.net-links')
    .selectAll('line')
    .data(netEdges, d => `${d.source}-${d.target}`);

  linkSel.exit().remove();

  const linkEnter = linkSel.enter().append('line')
    .attr('stroke-width', 1.2)
    .attr('stroke-opacity', 0.55)
    .attr('marker-end', d => {
      const srcState = stateMap[String(d.source)] || stateMap[String(d.source?.id)] || 'neutral';
      const tgtState = stateMap[String(d.target)] || stateMap[String(d.target?.id)] || 'neutral';
      return `url(#arrow-${srcState !== 'neutral' ? srcState : tgtState})`;
    });

  const linkMerge = linkEnter.merge(linkSel);
  linkMerge.each(function(d) {
    const srcState = stateMap[String(d.source?.id ?? d.source)] || 'neutral';
    const tgtState = stateMap[String(d.target?.id ?? d.target)] || 'neutral';
    const activeState = srcState !== 'neutral' ? srcState : tgtState;
    d3.select(this)
      .attr('stroke', STATE_COLOR[activeState] || '#5b8df6')
      .attr('stroke-dasharray', activeState === 'neutral' ? '2,3' : '4,3')
      .attr('marker-end', `url(#arrow-${activeState})`);
  });

  const nodeSel = netG.select('.net-nodes')
    .selectAll('g.net-node')
    .data(netNodes, d => d.id);

  nodeSel.exit().remove();

  const nodeEnter = nodeSel.enter().append('g')
    .attr('class', 'net-node')
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) netSim.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => {
        if (!event.active) netSim.alphaTarget(0);
        if (!document.getElementById('net-freeze-layout')?.checked) { d.fx = null; d.fy = null; }
      })
    );

  nodeEnter.append('circle').attr('r', d => d.isNeighbour ? 6 : 9).attr('stroke-width', 2);
  nodeEnter.append('text').attr('class', 'net-label').attr('x', 12).attr('y', 4)
    .attr('font-family', 'Space Mono, monospace').attr('font-size', '9px').attr('pointer-events', 'none');
  nodeEnter.append('title');

  const nodeMerge = nodeEnter.merge(nodeSel);
  nodeMerge.select('circle')
    .attr('r', d => d.isNeighbour ? 6 : 9)
    .attr('fill', d => STATE_COLOR[d.state] + (d.isNeighbour ? '55' : 'cc'))
    .attr('stroke', d => STATE_COLOR[d.state]);
  nodeMerge.select('text')
    .text(d => d.id)
    .style('display', showLabels ? null : 'none')
    .attr('fill', d => d.isNeighbour ? '#5b6080' : '#ccd6f0');
  nodeMerge.select('title')
    .text(d => `${d.id} · ${STATE_LABEL[d.state]}${d.isNeighbour ? ' (neighbour)' : ''}`);

  const svgEl = document.getElementById('net-svg');
  const W = svgEl.clientWidth  || 600;
  const H = svgEl.clientHeight || 460;

  netSim.nodes(netNodes).force('link').links(netEdges);
  netSim
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('x', d3.forceX(W / 2).strength(0.03))
    .force('y', d3.forceY(H / 2).strength(0.03));

  const freeze = document.getElementById('net-freeze-layout')?.checked;
  if (!freeze) {
    netSim.alpha(0.4).restart();
  } else {
    netSim.alpha(0.15).restart();
    setTimeout(() => netSim.alphaTarget(0).stop(), 1500);
  }
}

function netTick() {
  netG.select('.net-links').selectAll('line')
    .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  netG.select('.net-nodes').selectAll('g.net-node')
    .attr('transform', d => `translate(${d.x},${d.y})`);
}

// ── Run ───────────────────────────────────────────────────────────────────────
init();