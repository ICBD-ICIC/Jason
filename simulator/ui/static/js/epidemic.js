// agts.js — Agent state epidemiological dashboard
// Expects globals: AGENTS_DATA, FOLDER (injected by server template)
// Each agent's data is an array of log rows {timestamp, state?, ...}

// ── Constants ─────────────────────────────────────────────────────────────────
const STATES      = ['neutral', 'vaccinated', 'infected'];
const STATE_COLOR = { neutral: '#3a4055', vaccinated: '#2de89a', infected: '#f5604a' };
const STATE_LABEL = { neutral: 'Neutral', vaccinated: 'Vaccinated', infected: 'Infected' };

// ── Parse agent timelines ─────────────────────────────────────────────────────
// For each agent, extract the sequence of (timestamp, state) transitions.
// Then build a global sorted list of unique timestep checkpoints.

const agentNames = Object.keys(AGENTS_DATA);
const N = agentNames.length;

// agentTimelines[name] = sorted [{timestamp, state}]
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

// Build global timestep array: one entry per unique timestamp across all agents
const allTimestamps = new Set();
for (const name of agentNames) {
  const rows = AGENTS_DATA[name] || [];
  for (const row of rows) {
    if (row.timestamp != null) allTimestamps.add(row.timestamp);
  }
}
const sortedTimestamps = [...allTimestamps].sort((a, b) => a - b);

// Reduce to at most 300 steps for performance
const MAX_STEPS = 300;
function subsample(arr, maxN) {
  if (arr.length <= maxN) return arr;
  const step = arr.length / maxN;
  return Array.from({ length: maxN }, (_, i) => arr[Math.floor(i * step)]);
}
const steps = subsample(sortedTimestamps, MAX_STEPS);
const tMin = steps[0] ?? 0;
const tMax = steps[steps.length - 1] ?? 1;

// ── State at each step ────────────────────────────────────────────────────────
// getStateAt(name, ts) — last known state of agent at or before ts
function getStateAt(name, ts) {
  const tl = agentTimelines[name];
  if (!tl || !tl.length) return 'neutral';
  let state = 'neutral';
  for (const { timestamp, state: s } of tl) {
    if (timestamp <= ts) state = s;
    else break;
  }
  return state;
}

// Build step snapshots: for each step index, count states
// stateCounts[i] = {neutral, vaccinated, infected}
const stateCounts = steps.map(ts => {
  const counts = { neutral: 0, vaccinated: 0, infected: 0 };
  for (const name of agentNames) {
    const s = getStateAt(name, ts);
    counts[s] = (counts[s] || 0) + 1;
  }
  return counts;
});

// ── App state ──────────────────────────────────────────────────────────────────
let currentStep = steps.length - 1;
let playing = false;
let playTimer = null;
let playSpeed = 200; // ms between steps

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
  buildAgentDotGrid();
  buildScrubber();
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
        if (elements.length) {
          updateToStep(elements[0].index);
        }
      },
    },
  });
}

// Add vertical marker line for current step
function updateStackedMarker(stepIdx) {
  if (!stackedChart) return;
  stackedChart.options.plugins.annotation = {
    annotations: {
      line1: {
        type: 'line',
        xMin: stepIdx,
        xMax: stepIdx,
        borderColor: 'rgba(255,255,255,0.35)',
        borderWidth: 1,
        borderDash: [4, 4],
      }
    }
  };
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

  // Compute new infections per step (delta)
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

// ── Transition summary table ──────────────────────────────────────────────────
function buildTransitionsTable() {
  // Count all state transitions across all agents across all time
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

// ── Agent dot grid ────────────────────────────────────────────────────────────
function buildAgentDotGrid() {
  const grid = document.getElementById('agent-dot-grid');
  if (!grid) return;

  grid.innerHTML = agentNames.map((name, i) =>
    `<div class="agent-dot-cell neutral" id="dot-${i}" title="${name}" data-name="${name}"></div>`
  ).join('');
}

function updateDotGrid(ts) {
  for (let i = 0; i < agentNames.length; i++) {
    const el = document.getElementById(`dot-${i}`);
    if (!el) continue;
    const s = getStateAt(agentNames[i], ts);
    el.className = `agent-dot-cell ${s}`;
  }
}

// ── Computed metrics ──────────────────────────────────────────────────────────
function buildMetricsPanel(stepIdx) {
  const cur = stateCounts[stepIdx] || { neutral: 0, vaccinated: 0, infected: 0 };
  const inf = cur.infected;
  const vacc = cur.vaccinated;
  const neu = cur.neutral;

  // Peak infections
  const peak = Math.max(...stateCounts.map(c => c.infected));
  const peakStep = stateCounts.findIndex(c => c.infected === peak);
  const peakTime = steps[peakStep] ? fmtDateTime(steps[peakStep]) : '—';

  // Attack rate = cumulative infected / total
  // Approximate: final infected + vaccinated who were previously infected
  const attackRate = ((inf + vacc) / N * 100).toFixed(1);

  // Growth rate at this step
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
    { label: 'Infected now', val: inf.toLocaleString(), sub: ((inf/N)*100).toFixed(1)+'% of pop', cls: inf > 0 ? 'neg' : 'neu' },
    { label: 'Vaccinated now', val: vacc.toLocaleString(), sub: ((vacc/N)*100).toFixed(1)+'% of pop', cls: vacc > 0 ? 'pos' : 'neu' },
    { label: 'Susceptible', val: neu.toLocaleString(), sub: ((neu/N)*100).toFixed(1)+'% of pop', cls: 'neu' },
    { label: 'Peak infections', val: peak.toLocaleString(), sub: peakTime, cls: 'neg' },
    { label: 'Attack rate', val: attackRate+'%', sub: 'infected or vacc', cls: parseFloat(attackRate) > 50 ? 'neg' : parseFloat(attackRate) > 20 ? 'neu' : 'pos' },
    { label: 'Growth (Δ)', val: growthRate, sub: 'vs prev step', cls: (growthRate.startsWith('+') || growthRate.startsWith('∞')) ? 'neg' : 'pos' },
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

// ── Step badge ────────────────────────────────────────────────────────────────
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
  updateDotGrid(ts);
  updateScrubber(currentStep);
  updateStepBadge(currentStep);
  buildMetricsPanel(currentStep);
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

// ── Run ───────────────────────────────────────────────────────────────────────
init();
