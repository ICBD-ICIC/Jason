// polarization.js — polarization metrics + SVG tree
// Features:
//   1. Highest-score node highlighted with white glow
//   2. Click/right-click any node → context menu → remove node + subtree
//   3. Recompute scores after deletion; yellow border on changed nodes/components/breakdown
//   4. Undo stack (multiple levels) + reset
//   5. Improved tree layout: wraps wide forests into multiple rows
//
// Requires: utils.js, timeline.js
// Expects globals: MSGS, FOLDER (injected by server template)

// ── Index ─────────────────────────────────────────────────────────────────────
const byId = {};
for (const m of MSGS) byId[m.message.id] = m;

// ── Timeline ──────────────────────────────────────────────────────────────────
const timeline = new Timeline(MSGS, renderAll);

// ── Deletion / undo state ─────────────────────────────────────────────────────
let deletedIds  = new Set();   // all currently excluded message IDs
let undoStack   = [];          // [{ removedIds: Set, label: string }, ...]
let prevScoreMap = null;       // scoreMap before the last deletion (for diff highlights)
let changedNodeIds = new Set();// node IDs whose score changed after last deletion

// ── Metric state ──────────────────────────────────────────────────────────────
let currentMetric = 'discrete';
let currentResult = null;
let prevResult    = null;      // result before last deletion (for sidebar diff)

// ── Context menu state ────────────────────────────────────────────────────────
let menuNodeId = null;

// ── Active messages (timeline visible AND not deleted) ────────────────────────
function activeMsgs() {
  return timeline.visibleMsgs().filter(m => !deletedIds.has(m.message.id));
}

// ── Tree helpers ──────────────────────────────────────────────────────────────
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
  return { roots, kids: vKids, byId: vById };
}

function calcDepths(roots, kids) {
  const depth = {};
  function visit(m, d) { depth[m.message.id] = d; (kids[m.message.id] || []).forEach(c => visit(c, d + 1)); }
  roots.forEach(r => visit(r, 0));
  return depth;
}

// Collect all descendant IDs (inclusive) from a root within a set of msgs
function collectSubtree(rootId, msgs) {
  const vById = {}, vKids = {};
  for (const m of msgs) { vById[m.message.id] = m; vKids[m.message.id] = []; }
  for (const m of msgs) {
    const pid = m.message.original;
    if (pid != null && vById[pid]) vKids[pid].push(m);
  }
  const result = new Set();
  function visit(id) {
    result.add(id);
    for (const c of (vKids[id] || [])) visit(c.message.id);
  }
  visit(rootId);
  return result;
}

// ── Score helpers ─────────────────────────────────────────────────────────────
const getRelAbs = m => { const v = m.variables?.public?.relation_abs; return (v !== undefined && v !== null && v !== '') ? +v : null; };
const getImpact = m => {
  const votes = m.variables?.public?.votes;
  if (!Array.isArray(votes)) return null;
  const total = votes.reduce((s, v) => s + v, 0);
  return total === 0 ? 0 : votes.reduce((s, v, k) => s + k * v, 0) / total;
};

// Build a nodeId → score map for the current metric and a given message set
function buildScoreMap(msgs) {
  const metric = currentMetric;
  if (metric === 'discrete') {
    const map = {};
    for (const m of msgs) { const v = getRelAbs(m); if (v !== null) map[m.message.id] = v; }
    return map;
  }
  if (metric === 'continuous_args') {
    const { roots, kids } = buildTree(msgs);
    const depths   = calcDepths(roots, kids);
    const maxDepth = Math.max(0, ...Object.values(depths));
    const map = {};
    for (const m of msgs) {
      const rel = getRelAbs(m), imp = getImpact(m);
      if (rel === null || imp === null) continue;
      const dn = maxDepth > 0 ? (depths[m.message.id] || 0) / maxDepth : 0;
      map[m.message.id] = imp * dn * rel;
    }
    return map;
  }
  // continuous_ind
  const byAuthor = {};
  for (const m of msgs) {
    const rel = getRelAbs(m); if (rel === null) continue;
    const a = m.message.author || '(unknown)';
    (byAuthor[a] = byAuthor[a] || []).push(rel);
  }
  const xiMap = Object.fromEntries(Object.entries(byAuthor).map(([a, rs]) => [a, rs.reduce((s,r)=>s+r,0)/rs.length]));
  const map = {};
  for (const m of msgs) {
    const a = m.message.author || '(unknown)';
    if (xiMap[a] !== undefined) map[m.message.id] = xiMap[a];
  }
  return map;
}

// ── Deletion actions ──────────────────────────────────────────────────────────
function deleteSubtree(nodeId) {
  const msgs    = activeMsgs();
  const subtree = collectSubtree(nodeId, msgs);

  // Snapshot scores before deletion for diff
  prevScoreMap = buildScoreMap(msgs);
  prevResult   = currentResult;

  const m     = byId[nodeId];
  const label = m ? `#${nodeId} · ${m.message.author || '?'}` : `#${nodeId}`;
  undoStack.push({ removedIds: new Set(subtree), label });
  for (const id of subtree) deletedIds.add(id);

  // Compute which nodes changed score
  const newMsgs     = activeMsgs();
  const newScoreMap = buildScoreMap(newMsgs);
  changedNodeIds    = new Set();
  for (const [id, score] of Object.entries(newScoreMap)) {
    const prev = prevScoreMap[id];
    if (prev !== undefined && Math.abs(prev - score) > 1e-9) changedNodeIds.add(+id);
  }

  closeMenu();
  renderAll();
  updateUndoUI();
}

function undo() {
  if (!undoStack.length) return;
  undoStack.pop();
  // Rebuild deletedIds from remaining stack entries
  deletedIds = new Set();
  for (const entry of undoStack) for (const id of entry.removedIds) deletedIds.add(id);
  changedNodeIds = new Set();
  prevScoreMap   = null;
  prevResult     = null;
  renderAll();
  updateUndoUI();
}

function undoAll() {
  undoStack      = [];
  deletedIds     = new Set();
  changedNodeIds = new Set();
  prevScoreMap   = null;
  prevResult     = null;
  renderAll();
  updateUndoUI();
}

function updateUndoUI() {
  const section = document.getElementById('pol-undo-section');
  if (!section) return;

  const hasAny = undoStack.length > 0;
  section.style.display = hasAny ? '' : 'none';
  if (!hasAny) return;

  const last = undoStack[undoStack.length - 1];
  document.getElementById('pol-undo-label').textContent =
    `Removed: ${last.label}`;
  document.getElementById('pol-undo-count').textContent =
    undoStack.length > 1 ? `(${undoStack.length} deletions)` : '';

  const chips = document.getElementById('pol-deleted-chips');
  chips.innerHTML = undoStack.map(e =>
    `<span class="pol-deleted-chip">${esc(e.label)} · ${e.removedIds.size}n</span>`
  ).join('');

  const infoExcl = document.getElementById('info-excluded');
  if (infoExcl) infoExcl.textContent = deletedIds.size ? `${deletedIds.size} excluded` : '';
}

// ── Context menu ──────────────────────────────────────────────────────────────
function openMenu(e, nodeId) {
  e.preventDefault();
  e.stopPropagation();
  menuNodeId = nodeId;
  const m   = byId[nodeId];
  document.getElementById('pol-menu-title').textContent =
    m ? `#${nodeId} · ${m.message.author || '?'}` : `#${nodeId}`;
  const menu = document.getElementById('pol-node-menu');
  menu.classList.add('open');
  menu.style.left = (e.clientX + 4) + 'px';
  menu.style.top  = (e.clientY + 4) + 'px';
}

function closeMenu() {
  document.getElementById('pol-node-menu')?.classList.remove('open');
  menuNodeId = null;
}

function menuDeleteSubtree() {
  const id = menuNodeId;
  closeMenu();
  if (id !== null) deleteSubtree(id);
}

document.addEventListener('click', closeMenu);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });

// ── Polarization metrics ──────────────────────────────────────────────────────
function metricDiscrete(msgs) {
  const valid = msgs.filter(m => getRelAbs(m) !== null);
  if (!valid.length) return null;
  const n      = valid.length;
  const Aplus  = valid.filter(m => getRelAbs(m) === 1).length / n;
  const Aminus = 1 - Aplus;
  const deltaA = Math.abs(Aplus - Aminus);
  const mu     = (1 - deltaA) * 1;

  return {
    mu, d: 1, deltaA, Aplus, Aminus,
    scoreMap: Object.fromEntries(valid.map(m => [m.message.id, getRelAbs(m)])),
    breakdown: valid.map(m => ({ id: m.message.id, author: m.message.author, value: getRelAbs(m), label: `#${m.message.id} (${m.message.author})` })),
    breakdownType: 'argument',
    components: [
      { key: 'n (total args)',    val: n },
      { key: 'A⁺ (PRO fraction)', val: Aplus.toFixed(3),  cls: 'pos' },
      { key: 'A⁻ (CON fraction)', val: Aminus.toFixed(3), cls: 'neg' },
      { key: 'ΔA',                val: deltaA.toFixed(3) },
      { key: 'gc⁺',               val: '1.000',  cls: 'pos' },
      { key: 'gc⁻',               val: '−1.000', cls: 'neg' },
      { key: 'd (pole distance)', val: '1.000' },
    ],
  };
}

function metricContinuousArgs(msgs, depths, maxDepth) {
  const valid = [];
  for (const m of msgs) {
    const rel = getRelAbs(m), imp = getImpact(m);
    if (rel === null || imp === null) continue;
    const depthNorm = maxDepth > 0 ? (depths[m.message.id] || 0) / maxDepth : 0;
    valid.push({ m, score: imp * depthNorm * rel, rel, imp, depthNorm });
  }
  if (!valid.length) return null;

  const n       = valid.length;
  const pos     = valid.filter(x => x.score > 0);
  const neg     = valid.filter(x => x.score < 0);
  const Aplus   = pos.length / n;
  const Aminus  = neg.length / n;
  const deltaA  = Math.abs(Aplus - Aminus);
  const gcPlus  = pos.length ? pos.reduce((s, x) => s + x.score, 0) / pos.length : null;
  const gcMinus = neg.length ? neg.reduce((s, x) => s + x.score, 0) / neg.length : null;
  const d       = (gcPlus !== null && gcMinus !== null) ? Math.abs(gcPlus - gcMinus) / 2 : 0;
  const mu      = (gcPlus !== null && gcMinus !== null) ? (1 - deltaA) * d : 0;

  return {
    mu, d, deltaA, Aplus, Aminus, gcPlus, gcMinus,
    scoreMap: Object.fromEntries(valid.map(({ m, score }) => [m.message.id, score])),
    breakdown: valid.map(({ m, score, imp, depthNorm }) => ({
      id: m.message.id, author: m.message.author, value: score,
      label: `#${m.message.id} (${m.message.author})`,
      extra: `imp=${imp.toFixed(2)} depth=${depthNorm.toFixed(2)}`,
    })),
    breakdownType: 'argument',
    components: [
      { key: 'n (total args)',   val: n },
      { key: 'A⁺ (score>0)',     val: Aplus.toFixed(3),  cls: 'pos' },
      { key: 'A⁻ (score<0)',     val: Aminus.toFixed(3), cls: 'neg' },
      { key: 'ΔA',               val: deltaA.toFixed(3) },
      { key: 'gc⁺',              val: gcPlus  !== null ? gcPlus.toFixed(3)  : '—', cls: 'pos' },
      { key: 'gc⁻',              val: gcMinus !== null ? gcMinus.toFixed(3) : '—', cls: 'neg' },
      { key: 'd (pole distance)', val: d.toFixed(3) },
    ],
  };
}

function metricContinuousInd(msgs) {
  const byAuthor = {};
  for (const m of msgs) {
    const rel = getRelAbs(m); if (rel === null) continue;
    const a = m.message.author || '(unknown)';
    (byAuthor[a] = byAuthor[a] || []).push(rel);
  }
  const individuals = Object.entries(byAuthor).map(([author, rels]) => ({
    author, xi: rels.reduce((s, r) => s + r, 0) / rels.length, count: rels.length,
  }));
  const N = individuals.length; if (!N) return null;

  const pos     = individuals.filter(i => i.xi > 0);
  const neg     = individuals.filter(i => i.xi < 0);
  const Aplus   = pos.length / N;
  const Aminus  = neg.length / N;
  const deltaA  = Math.abs(Aplus - Aminus);
  const gcPlus  = pos.length ? pos.reduce((s, i) => s + i.xi, 0) / pos.length : null;
  const gcMinus = neg.length ? neg.reduce((s, i) => s + i.xi, 0) / neg.length : null;
  const d       = (gcPlus !== null && gcMinus !== null) ? Math.abs(gcPlus - gcMinus) / 2 : 0;
  const mu      = (gcPlus !== null && gcMinus !== null) ? (1 - deltaA) * d : 0;
  const xiMap   = Object.fromEntries(individuals.map(i => [i.author, i.xi]));

  return {
    mu, d, deltaA, Aplus, Aminus, gcPlus, gcMinus,
    xiMap,
    scoreMap: (() => {
      const map = {};
      for (const m of msgs) {
        const a = m.message.author || '(unknown)';
        if (xiMap[a] !== undefined) map[m.message.id] = xiMap[a];
      }
      return map;
    })(),
    breakdown: individuals.sort((a, b) => a.xi - b.xi).map(i => ({
      id: null, author: i.author, value: i.xi, label: i.author,
      extra: `${i.count} arg${i.count !== 1 ? 's' : ''}`,
    })),
    breakdownType: 'individual',
    components: [
      { key: 'N (individuals)',   val: N },
      { key: 'A⁺ (xi > 0)',       val: Aplus.toFixed(3),  cls: 'pos' },
      { key: 'A⁻ (xi < 0)',       val: Aminus.toFixed(3), cls: 'neg' },
      { key: 'ΔA',                val: deltaA.toFixed(3) },
      { key: 'gc⁺',               val: gcPlus  !== null ? gcPlus.toFixed(3)  : '—', cls: 'pos' },
      { key: 'gc⁻',               val: gcMinus !== null ? gcMinus.toFixed(3) : '—', cls: 'neg' },
      { key: 'd (pole distance)',  val: d.toFixed(3) },
    ],
  };
}

// ── Node coloring ─────────────────────────────────────────────────────────────
function lerpColor(c1, c2, t) {
  const parse = c => [parseInt(c.slice(1,3),16), parseInt(c.slice(3,5),16), parseInt(c.slice(5,7),16)];
  const [a, b] = [parse(c1), parse(c2)];
  return `rgb(${a.map((v,i) => Math.round(v + (b[i]-v)*t)).join(',')})`;
}

function nodeColor(m, result) {
  const rel    = +(m.variables?.public?.relation ?? 0);
  const relAbs = getRelAbs(m);
  if (rel === 0) return '#5b8df6';

  if (currentMetric === 'continuous_args' && result?.scoreMap) {
    const s = result.scoreMap[m.message.id];
    if (s === undefined) return '#7a82a0';
    return s > 0 ? lerpColor('#3dffd0', '#2de89a', Math.min(1, s))
         : s < 0 ? lerpColor('#f5604a', '#cc2200', Math.min(1, -s))
         : '#7a82a0';
  }
  if (relAbs === 1)  return '#2de89a';
  if (relAbs === -1) return '#f5604a';
  return '#7a82a0';
}

function indColor(m, result) {
  const rel = +(m.variables?.public?.relation ?? 0);
  if (rel === 0) return '#5b8df6';
  if (!result?.xiMap) return nodeColor(m, result);
  const xi = result.xiMap[m.message.author];
  if (xi === undefined) return '#7a82a0';
  return xi > 0 ? lerpColor('#3dffd0', '#2de89a', Math.min(1, xi))
       : xi < 0 ? lerpColor('#f5604a', '#cc2200', Math.min(1, -xi))
       : '#7a82a0';
}

// ── SVG layout — Feature 5: row-wrapping ──────────────────────────────────────
// When root-level trees are too wide collectively, wrap them into multiple rows.
const NODE_R = 10, H_GAP = 34, MIN_W_GAP = 22;
const MAX_ROW_PX = 1400; // max width before wrapping to next row

function layoutTree(roots, kids) {
  // 1. Compute subtree widths bottom-up
  const subtreeW = {};
  function computeW(m) {
    const ch = kids[m.message.id] || [];
    if (!ch.length) { subtreeW[m.message.id] = NODE_R * 2; return; }
    ch.forEach(computeW);
    subtreeW[m.message.id] = Math.max(NODE_R * 2,
      ch.reduce((s, c) => s + subtreeW[c.message.id], 0) + MIN_W_GAP * (ch.length - 1));
  }
  roots.forEach(computeW);

  // 2. Assign roots to rows so no row exceeds MAX_ROW_PX
  const TREE_GAP = MIN_W_GAP * 4;
  const rows = [];
  let rowRoots = [], rowWidth = 0;
  for (const r of roots) {
    const w = subtreeW[r.message.id];
    if (rowRoots.length > 0 && rowWidth + TREE_GAP + w > MAX_ROW_PX) {
      rows.push(rowRoots);
      rowRoots = [r]; rowWidth = w;
    } else {
      rowRoots.push(r);
      rowWidth += (rowRoots.length > 1 ? TREE_GAP : 0) + w;
    }
  }
  if (rowRoots.length) rows.push(rowRoots);

  // 3. Place each row
  const positions = {};
  let yOffset = 0;

  for (const rowGroup of rows) {
    // max depth in this row (for row height)
    let rowMaxDepth = 0;
    function maxD(m, d) { rowMaxDepth = Math.max(rowMaxDepth, d); (kids[m.message.id]||[]).forEach(c => maxD(c, d+1)); }
    rowGroup.forEach(r => maxD(r, 0));
    const rowH = (rowMaxDepth + 1) * (NODE_R * 2 + H_GAP);

    function place(m, left, depth) {
      const ch = kids[m.message.id] || [];
      const y  = yOffset + depth * (NODE_R * 2 + H_GAP) + NODE_R + 16;
      let x;
      if (!ch.length) {
        x = left + subtreeW[m.message.id] / 2;
      } else {
        let cursor = left;
        ch.forEach(c => { place(c, cursor, depth + 1); cursor += subtreeW[c.message.id] + MIN_W_GAP; });
        x = (positions[ch[0].message.id].x + positions[ch[ch.length-1].message.id].x) / 2;
      }
      positions[m.message.id] = { x, y };
    }

    let cursor = 0;
    for (const r of rowGroup) {
      place(r, cursor, 0);
      cursor += subtreeW[r.message.id] + TREE_GAP;
    }

    yOffset += rowH + H_GAP * 2.5;
  }

  return positions;
}

// ── Main render ───────────────────────────────────────────────────────────────
function renderAll() {
  const msgs = activeMsgs();
  if (!msgs.length) {
    document.getElementById('pol-svg-container').innerHTML =
      `<div class="pol-empty"><div class="pol-empty-icon">⬡</div><div>No messages in selected time range.</div></div>`;
    updateSidebar(null);
    updateInfoBar([], {}, 0);
    return;
  }

  const { roots, kids } = buildTree(msgs);
  const depths   = calcDepths(roots, kids);
  const maxDepth = Math.max(0, ...Object.values(depths));

  let result = null;
  if      (currentMetric === 'discrete')        result = metricDiscrete(msgs);
  else if (currentMetric === 'continuous_args') result = metricContinuousArgs(msgs, depths, maxDepth);
  else if (currentMetric === 'continuous_ind')  result = metricContinuousInd(msgs);
  currentResult = result;

  // Feature 1: find node with highest absolute score
  let highestId = null, highestAbsScore = -Infinity;
  if (result?.scoreMap) {
    for (const [id, score] of Object.entries(result.scoreMap)) {
      const abs = Math.abs(+score);
      if (abs > highestAbsScore) { highestAbsScore = abs; highestId = +id; }
    }
  }

  const positions = layoutTree(roots, kids);
  const xs = Object.values(positions).map(p => p.x);
  const ys = Object.values(positions).map(p => p.y);
  const svgW = Math.max(600, (xs.length ? Math.max(...xs) : 0) + NODE_R + 24);
  const svgH = Math.max(300, (ys.length ? Math.max(...ys) : 0) + NODE_R + 24);

  let edgesHTML = '', nodesHTML = '';

  // Edges
  for (const m of msgs) {
    const ch = kids[m.message.id] || [], p = positions[m.message.id];
    if (!p) continue;
    for (const c of ch) {
      const cp = positions[c.message.id]; if (!cp) continue;
      const [x1, y1, x2, y2] = [p.x, p.y + NODE_R, cp.x, cp.y - NODE_R];
      const cy1 = y1 + (y2-y1)*.4, cy2 = y1 + (y2-y1)*.6;
      edgesHTML += `<path class="pol-edge" d="M${x1},${y1} C${x1},${cy1} ${x2},${cy2} ${x2},${y2}"/>`;
    }
  }

  // Nodes
  for (const m of msgs) {
    const p = positions[m.message.id]; if (!p) continue;
    const mid        = m.message.id;
    const fillColor  = currentMetric === 'continuous_ind' ? indColor(m, result) : nodeColor(m, result);
    const rel        = +(m.variables?.public?.relation ?? 0);
    const relAbs     = getRelAbs(m);
    const relLabel   = rel === 0 ? 'ROOT' : relAbs === 1 ? 'PRO' : relAbs === -1 ? 'CON' : '?';
    const imp        = getImpact(m);
    const depthN     = maxDepth > 0 ? (depths[mid] || 0) / maxDepth : 0;
    const isHighest  = mid === highestId;                   // Feature 1
    const isChanged  = changedNodeIds.has(mid);             // Feature 3

    let scoreStr = '';
    if (currentMetric === 'continuous_args' && result?.scoreMap) {
      const s = result.scoreMap[mid];
      scoreStr = s !== undefined ? `score: ${(+s).toFixed(3)}` : '';
    } else if (currentMetric === 'continuous_ind' && result?.xiMap) {
      const xi = result.xiMap[m.message.author];
      scoreStr = xi !== undefined ? `author xi: ${xi.toFixed(3)}` : '';
    } else {
      scoreStr = `rel_abs: ${relAbs ?? '—'}`;
    }

    const tipData = JSON.stringify({
      id: mid, author: m.message.author, rel: relLabel,
      depth: depths[mid] || 0, imp: imp !== null ? imp.toFixed(3) : '—',
      score: scoreStr, depthN: depthN.toFixed(3),
      isHighest, isChanged,
    }).replace(/"/g, '&quot;');

    // Feature 1: white glow for highest score node (SVG filter)
    const filterAttr = isHighest ? 'filter="url(#pol-glow-white)"' : '';

    // Feature 3: yellow dashed stroke for changed nodes
    let strokeColor = fillColor, strokeWidth = 2, strokeDash = '';
    if (isChanged) {
      strokeColor  = '#f0c040';
      strokeWidth  = 2.5;
      strokeDash   = 'stroke-dasharray="4 2"';
    }

    // Feature 1: outer ring for highest
    const outerRing = isHighest
      ? `<circle cx="${p.x}" cy="${p.y}" r="${NODE_R + 5}" fill="none"
           stroke="rgba(255,255,255,0.45)" stroke-width="1.5" pointer-events="none"/>`
      : '';

    nodesHTML += `
      <g class="pol-node" data-id="${mid}" data-tip="${tipData}"
         onmouseenter="showTip(event,this)" onmouseleave="hideTip()"
         onclick="openMenu(event,${mid})" oncontextmenu="openMenu(event,${mid})">
        ${outerRing}
        <circle cx="${p.x}" cy="${p.y}" r="${NODE_R}"
          fill="${fillColor}" fill-opacity="0.85"
          stroke="${strokeColor}" stroke-width="${strokeWidth}" ${strokeDash} ${filterAttr}/>
      </g>`;
  }

  document.getElementById('pol-svg-container').innerHTML = `
    <svg id="pol-svg"
         viewBox="0 0 ${svgW} ${svgH}"
         xmlns="http://www.w3.org/2000/svg"
         width="${svgW}" height="${svgH}"
         style="background:transparent;display:block;min-width:100%;">
      <defs>
        <filter id="pol-glow-white" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="3.5" result="blur"/>
          <feFlood flood-color="white" flood-opacity="0.65" result="color"/>
          <feComposite in="color" in2="blur" operator="in" result="glow"/>
          <feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <style>
        .pol-edge { stroke: #2a3045; stroke-width: 1.5; fill: none; opacity: .7; }
        .pol-node { cursor: pointer; }
        .pol-node circle { transition: r .1s; }
        .pol-node:hover > circle:last-of-type { r: ${NODE_R + 2}; }
      </style>
      <g id="pol-edges">${edgesHTML}</g>
      <g id="pol-nodes">${nodesHTML}</g>
    </svg>`;

  // SVG container needs explicit width so horizontal scroll works
  const container = document.getElementById('pol-svg-container');
  container.style.width    = svgW + 'px';
  container.style.minWidth = '100%';

  updateInfoBar(msgs, depths, maxDepth);
  updateSidebar(result);
  document.getElementById('hdr-count').textContent = `${msgs.length} messages`;
}

// ── Sidebar update — Feature 3: yellow highlights ─────────────────────────────
function updateSidebar(result) {
  const metricNames = { discrete: 'Discrete Arguments', continuous_args: 'Continuous Arguments', continuous_ind: 'Continuous Individuals' };
  document.getElementById('scalar-label').textContent = metricNames[currentMetric] || '';

  if (!result) {
    document.getElementById('scalar-value').textContent = '—';
    document.getElementById('scalar-value').style.color = 'var(--text)';
    document.getElementById('scalar-bar').style.width   = '0%';
    document.getElementById('scalar-sub').textContent   = 'No valid data for this metric.';
    document.getElementById('pol-components').innerHTML = '<div class="pol-no-data">No data.</div>';
    document.getElementById('pol-components').classList.remove('score-changed');
    document.getElementById('breakdown-list').innerHTML = '<div class="pol-no-data">No data.</div>';
    document.getElementById('pol-breakdown').classList.remove('score-changed');
    prevResult = null;
    return;
  }

  const scalarVal = document.getElementById('scalar-value');
  scalarVal.textContent = result.mu.toFixed(4);
  scalarVal.style.color = result.mu < 0.25 ? 'var(--pro)' : result.mu < 0.5 ? '#f0a500' : 'var(--con)';
  document.getElementById('scalar-bar').style.width = (result.mu * 100).toFixed(1) + '%';
  document.getElementById('scalar-sub').textContent = `μ = ${result.mu.toFixed(4)} · d = ${result.d.toFixed(4)} · ΔA = ${result.deltaA.toFixed(4)}`;

  // Build prev-component lookup for diff
  const prevCompMap = {};
  if (prevResult?.components) for (const c of prevResult.components) prevCompMap[c.key] = c.val;

  let anyCompChanged = false;
  const compHTML = result.components.map(c => {
    const prevVal = prevCompMap[c.key];
    const changed = prevVal !== undefined && String(prevVal) !== String(c.val);
    if (changed) anyCompChanged = true;
    return `<div class="pol-comp-row${changed ? ' score-changed' : ''}">
      <span class="pol-comp-key">${esc(c.key)}</span>
      <span class="pol-comp-val ${c.cls||''}">${esc(String(c.val))}${
        changed ? `<span class="pol-comp-was">was ${esc(String(prevVal))}</span>` : ''
      }</span>
    </div>`;
  }).join('');
  const compEl = document.getElementById('pol-components');
  compEl.innerHTML = compHTML;
  compEl.classList.toggle('score-changed', anyCompChanged);

  // Breakdown
  const isInd = result.breakdownType === 'individual';
  document.getElementById('breakdown-label').textContent = isInd ? 'Per-individual breakdown' : 'Per-argument breakdown';
  document.getElementById('breakdown-head').textContent  = isInd ? 'Author · xᵢ · args' : 'Argument · value';

  // Build prev-breakdown lookup
  const prevBdMap = {};
  if (prevResult?.breakdown) {
    for (const item of prevResult.breakdown) {
      const key = item.id !== null ? item.id : item.author;
      prevBdMap[key] = item.value;
    }
  }

  let anyBdChanged = false;
  const bdHTML = (!result.breakdown?.length)
    ? '<div class="pol-no-data">No data.</div>'
    : [...result.breakdown].sort((a, b) => b.value - a.value).map(item => {
        const color  = item.value > 0 ? '#2de89a' : item.value < 0 ? '#f5604a' : '#7a82a0';
        const key    = item.id !== null ? item.id : item.author;
        const prevV  = prevBdMap[key];
        const changed = prevV !== undefined && Math.abs(+prevV - +item.value) > 1e-9;
        if (changed) anyBdChanged = true;
        return `<div class="pol-breakdown-item${changed ? ' score-changed' : ''}">
          <div class="pol-bd-dot" style="background:${color}"></div>
          <div class="pol-bd-name" title="${esc(item.label)}">${esc(item.label)}</div>
          <div class="pol-bd-val">${typeof item.value === 'number' ? item.value.toFixed(3) : esc(String(item.value))}${
            changed ? `<span class="pol-bd-was">was ${(+prevV).toFixed(3)}</span>` : ''
          }${item.extra ? `<br><span style="color:var(--muted);font-size:.62rem">${esc(item.extra)}</span>` : ''}
          </div>
        </div>`;
      }).join('');

  document.getElementById('breakdown-list').innerHTML = bdHTML;
  document.getElementById('pol-breakdown').classList.toggle('score-changed', anyBdChanged);

  prevResult = result;
}

function updateInfoBar(msgs, depths, maxDepth) {
  const authors = new Set(msgs.map(m => m.message.author));
  document.getElementById('info-nodes').textContent   = msgs.length;
  document.getElementById('info-edges').textContent   = msgs.filter(m => +(m.variables?.public?.relation ?? 0) !== 0).length;
  document.getElementById('info-depth').textContent   = maxDepth;
  document.getElementById('info-authors').textContent = authors.size;
  const excl = document.getElementById('info-excluded');
  if (excl) excl.textContent = deletedIds.size ? `${deletedIds.size} excluded` : '';
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
const tooltip = document.getElementById('pol-tooltip');

function showTip(e, el) {
  let d; try { d = JSON.parse(el.dataset.tip.replace(/&quot;/g, '"')); } catch { return; }
  tooltip.innerHTML = `
    <div class="pol-tooltip-title">#${d.id} · ${esc(d.author)}</div>
    <div>Relation: <b>${esc(d.rel)}</b></div>
    <div>Depth: ${d.depth}</div>
    <div>Impact: ${esc(d.imp)}</div>
    <div>${esc(d.score)}</div>
    ${d.isHighest ? `<div style="color:#fff;margin-top:4px">⭐ Highest score node</div>` : ''}
    ${d.isChanged ? `<div style="color:#f0c040;margin-top:2px">⚡ Score changed after deletion</div>` : ''}
    <div class="pol-tooltip-hint">Click or right-click to remove subtree</div>`;
  tooltip.style.display = 'block';
  moveTip(e);
}
function moveTip(e)  { tooltip.style.left = (e.clientX + 14) + 'px'; tooltip.style.top = (e.clientY + 14) + 'px'; }
function hideTip()   { tooltip.style.display = 'none'; }
document.addEventListener('mousemove', e => { if (tooltip.style.display === 'block') moveTip(e); });

// ── Metric change ─────────────────────────────────────────────────────────────
function onMetricChange() {
  currentMetric  = document.getElementById('metric-select').value;
  prevResult     = null;
  changedNodeIds = new Set();
  renderAll();
}

// ── Boot ──────────────────────────────────────────────────────────────────────
renderAll();
