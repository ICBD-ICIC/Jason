// arg_tree.js — tree rendering + BAF panel
// Requires: utils.js, timeline.js, baf.js
// Expects globals: MSGS, FOLDER (injected by server template)

// ── Index ─────────────────────────────────────────────────────────────────────
const byId = {};
for (const m of MSGS) {
  byId[m.message.id] = m;
}

// ── Timeline ──────────────────────────────────────────────────────────────────
const timeline = new Timeline(MSGS, render);

// ── Tree state ────────────────────────────────────────────────────────────────
let collapsed    = {};
let currentKids  = {};
let bafLabels    = {};  // id → 'in' | 'out' | 'undecided'

// ── Tree rendering ────────────────────────────────────────────────────────────
function buildTree(msgs) {
  const vById = {}, vKids = {};
  for (const m of msgs) { vById[m.message.id] = m; vKids[m.message.id] = []; }

  const roots = [];
  for (const m of msgs) {
    const rel = +(m.variables?.public?.relation ?? 0);
    const pid = m.message.original;
    if (rel === 0 || pid == null || !vById[pid]) roots.push(m);
    else vKids[pid].push(m);
  }
  const byTs = (a, b) => (a.message.timestamp || 0) - (b.message.timestamp || 0);
  roots.sort(byTs);
  for (const id in vKids) vKids[id].sort(byTs);
  return { roots, vKids, vById };
}

function render() {
  const el   = document.getElementById('tree-root');
  const msgs = timeline.visibleMsgs();

  if (!msgs.length) {
    el.innerHTML = '<div class="empty">No messages in log.</div>';
    updateStats(msgs); return;
  }

  const { roots, vKids } = buildTree(msgs);
  currentKids = vKids;

  el.innerHTML = `<div class="tree-list">${
    roots.map(r => `<div class="thread">${renderNode(r, vKids)}</div>`).join('')
  }</div>`;
  updateStats(msgs);
}

function renderNode(m, vKids) {
  const id      = m.message.id;
  const rel     = +(m.variables?.public?.relation ?? 0);
  const ck      = vKids[id] || [];
  const isColl  = collapsed[id] ?? false;
  const relCls  = rel === 0 ? 'root' : rel === 1 ? 'pro' : 'con';
  const relLbl  = rel === 0 ? 'ROOT' : rel === 1 ? '✦ PRO' : '✗ CON';
  const ts      = m.message.timestamp ? new Date(m.message.timestamp).toLocaleString([],
    { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '';
  const proC    = ck.filter(c => +(c.variables?.public?.relation ?? 0) === 1).length;
  const conC    = ck.filter(c => +(c.variables?.public?.relation ?? 0) === -1).length;

  const reactions = (m.message.reactions || []).map(r => `<span class="reaction">${esc(String(r))}</span>`).join('');
  const topics    = (m.topics || []).map(t => `<span class="topic">${esc(String(t))}</span>`).join('');
  const vars      = renderVars(m.variables);

  const bafCls = bafLabels[id]
    ? ({ in: ' baf-accepted', out: ' baf-rejected', undecided: ' baf-undecided' }[bafLabels[id]] ?? '')
    : '';
  const doHighlight = document.getElementById('baf-highlight')?.checked;

  const bafBadge = (bafLabels[id] && doHighlight) ? (() => {
    const [bg, color] = bafLabels[id] === 'in'
      ? ['rgba(45,232,154,.18)', 'var(--pro)']
      : bafLabels[id] === 'out'
      ? ['rgba(245,96,74,.18)',  'var(--con)']
      : ['rgba(255,204,0,.18)',  '#9a7c00'];
    return `<span class="badge" style="background:${bg};color:${color}">BAF:${bafLabels[id].toUpperCase()}</span>`;
  })() : '';

  const foot = (ck.length || reactions || vars) ? `
    <div class="node-foot">
      ${ck.length ? `<span class="child-cnt">
        ${proC ? `<span class="p">▲${proC}</span>` : ''}
        ${conC ? `<span class="c">▼${conC}</span>` : ''}
        ${!proC && !conC ? `<span>${ck.length} repl.</span>` : ''}
      </span>` : ''}
      ${reactions ? `<span class="reactions">${reactions}</span>` : ''}
      ${vars ? `<button class="foot-btn" onclick="toggleVars(${id},event)">⬡ vars</button>` : ''}
      ${ck.length ? `<button class="foot-btn" onclick="toggleNode(${id},event)">${isColl ? '▸ expand' : '▾ collapse'}</button>` : ''}
    </div>` : '';

  const card = `
    <div class="node-card ${relCls}${doHighlight ? bafCls : ''}" id="card-${id}">
      <div class="node-meta">
        <span class="badge ${relCls}">${relLbl}</span>
        ${m.variables?.generated ? `<span class="badge">GENERATED</span>` : ''}
        ${bafBadge}
        <span class="author">${esc(m.message.author)}</span>
        <span class="msg-id">#${id}</span>
        ${ts ? `<span class="ts">${esc(ts)}</span>` : ''}
      </div>
      <div class="node-body">${esc(m.message.content)}</div>
      ${topics ? `<div class="topics">${topics}</div>` : ''}
      ${vars ? `<div class="vars-panel" id="vp-${id}"><div class="vars-grid">${vars}</div></div>` : ''}
      ${foot}
    </div>`;

  const children = (ck.length && !isColl)
    ? `<div class="children">${ck.map(c => `<div class="child-item">${renderNode(c, vKids)}</div>`).join('')}</div>`
    : '';

  return `<div class="node-wrap" data-id="${id}" data-rel="${rel}">${card}${children}</div>`;
}

function renderVars(variables) {
  if (!variables) return '';
  return Object.entries(variables)
    .filter(([k]) => k !== 'relation')
    .map(([k, v]) => {
      let display = (v instanceof Map) ? JSON.stringify(Object.fromEntries(v), null, 2)
                  : (v !== null && typeof v === 'object') ? JSON.stringify(v, null, 2)
                  : String(v);
      const multiline = display.includes('\n');
      return `<span class="var-kv"><span class="var-k">${esc(k)}: </span>` +
             (multiline ? `<pre class="var-v var-v-block">${esc(display)}</pre>`
                        : `<span class="var-v">${esc(display)}</span>`) +
             `</span>`;
    }).join('');
}

// ── Tree controls ─────────────────────────────────────────────────────────────
function toggleNode(id, e) { e.stopPropagation(); collapsed[id] = !collapsed[id]; render(); }
function toggleVars(id, e) { e.stopPropagation(); document.getElementById(`vp-${id}`)?.classList.toggle('open'); }
function expandAll()       { collapsed = {}; render(); }
function collapseAll()     { for (const id in currentKids) if ((currentKids[id] || []).length) collapsed[id] = true; render(); }

function updateStats(msgs = MSGS) {
  const rs   = msgs.filter(m => +(m.variables?.public?.relation ?? 0) === 0).length;
  const pros  = msgs.filter(m => +(m.variables?.public?.relation ?? 0) === 1).length;
  const cons  = msgs.filter(m => +(m.variables?.public?.relation ?? 0) === -1).length;
  document.getElementById('hdr-stats').innerHTML = `
    <span class="stat"><span class="stat-dot" style="background:var(--accent)"></span>${rs} root${rs!==1?'s':''}</span>
    <span class="stat"><span class="stat-dot" style="background:var(--pro)"></span>${pros} pro</span>
    <span class="stat"><span class="stat-dot" style="background:var(--con)"></span>${cons} con</span>
    <span class="stat" style="margin-left:4px;color:var(--muted)">${msgs.length} total</span>`;
}

// ── BAF Panel ──────────────────────────────────────────────────────────────────
function toggleBafPanel() {
  const panel = document.getElementById('baf-panel');
  const btn   = document.getElementById('baf-toggle-btn');
  const isOpen = panel.classList.toggle('open');
  btn.classList.toggle('active', isOpen);
  document.body.classList.toggle('baf-open', isOpen);
}

function runBaf() {
  const scope      = document.getElementById('baf-scope').value;
  const semantics  = document.getElementById('baf-semantics').value;
  const weightMode = document.getElementById('baf-weight').value;
  const proRole    = document.getElementById('baf-pro-role').value;
  const rootsIn    = document.getElementById('baf-roots-in')?.checked ?? true;

  const msgs = scope === 'visible' ? timeline.visibleMsgs() : MSGS;
  if (!msgs.length) {
    document.getElementById('baf-results').innerHTML = '<div class="baf-empty">No messages to evaluate.</div>';
    return;
  }

  const { nodes, attacks, supports } = buildFramework(msgs, weightMode, proRole);
  let status;
  try {
    status = runSemantics(semantics, nodes, attacks, supports, rootsIn);
  } catch (e) {
    document.getElementById('baf-results').innerHTML =
      `<div class="baf-empty">Computation error: ${esc(e.message)}</div>`;
    return;
  }

  bafLabels = status;
  render();
  renderBafResults(nodes, status, attacks);
}

function renderBafResults(nodes, status, attacks) {
  const { proScore, conScore } = computeWinner(nodes, status);
  const inArgs  = Object.entries(status).filter(([, s]) => s === 'in').map(([id]) => +id);
  const outArgs = Object.entries(status).filter(([, s]) => s === 'out').map(([id]) => +id);
  const undArgs = Object.entries(status).filter(([, s]) => s === 'undecided').map(([id]) => +id);

  const winner   = proScore > conScore ? 'pro' : conScore > proScore ? 'con' : 'tie';
  const winLabel = { pro: '✦ PRO side winning', con: '✗ CON side winning', tie: '⚖ Debate is balanced (tie)' }[winner];
  const winSub   = winner === 'tie'
    ? 'Neither side has a dominant accepted argument cluster.'
    : `Accepted ${winner.toUpperCase()} arguments outweigh the other side (${
        winner === 'pro' ? proScore.toFixed(2)+' vs '+conScore.toFixed(2)
                        : conScore.toFixed(2)+' vs '+proScore.toFixed(2)}).`;

  const argItem = (id) => {
    const n       = nodes[id]; if (!n) return '';
    const lbl     = status[id];
    const snippet = n.content ? esc(n.content.slice(0, 80)) + (n.content.length > 80 ? '…' : '') : '(no content)';
    return `<li class="baf-arg-item" onclick="scrollToCard(${id})" title="Click to scroll to #${id}">
      <div class="baf-dot ${lbl}"></div>
      <div>
        <div class="baf-arg-text">${snippet}</div>
        <div class="baf-arg-id">#${id} · ${n.rel===0?'root':n.rel===1?'pro':'con'}</div>
      </div>
    </li>`;
  };

  const section = (label, ids) => ids.length ? `
    <div class="baf-section-lbl">${label}</div>
    <ul class="baf-arg-list">${ids.map(argItem).join('')}</ul>` : '';

  document.getElementById('baf-results').innerHTML = `
    <div class="baf-legend">
      <div class="baf-leg-item"><div class="baf-dot in"></div> IN (accepted)</div>
      <div class="baf-leg-item"><div class="baf-dot out"></div> OUT (rejected)</div>
      <div class="baf-leg-item"><div class="baf-dot undecided"></div> Undecided</div>
    </div>
    <div class="baf-winner-box ${winner}">
      <div class="baf-winner-title">${winLabel}</div>
      <div>${winSub}</div>
    </div>
    <div class="baf-stat-row">
      <div class="baf-stat"><div class="baf-stat-n" style="color:var(--pro)">${inArgs.length}</div><div class="baf-stat-lbl">IN</div></div>
      <div class="baf-stat"><div class="baf-stat-n" style="color:var(--con)">${outArgs.length}</div><div class="baf-stat-lbl">OUT</div></div>
      <div class="baf-stat"><div class="baf-stat-n" style="color:#ffcc00">${undArgs.length}</div><div class="baf-stat-lbl">Undecided</div></div>
      <div class="baf-stat"><div class="baf-stat-n">${attacks.length}</div><div class="baf-stat-lbl">Attacks</div></div>
    </div>
    ${section('Accepted (IN)', inArgs)}
    ${section('Rejected (OUT)', outArgs)}
    ${section('Undecided', undArgs)}`;
}

function scrollToCard(id) {
  // Uncollapse ancestors if needed then scroll
  let node = document.querySelector(`[data-id="${id}"]`);
  if (!node) {
    // try to find and uncollapse a parent
    for (const pid in collapsed) {
      if (collapsed[pid]) { collapsed[pid] = false; }
    }
    render();
  }
  setTimeout(() => {
    const target = document.getElementById('card-' + id);
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 80);
}

// ── Boot ──────────────────────────────────────────────────────────────────────
render();
