// baf.js — Bipolar Argumentation Framework semantics

/**
 * Build an attack/support framework from a set of messages.
 * Returns { nodes, attacks, supports }
 */
function buildFramework(msgs, weightMode, proRole) {
  const ids   = new Set(msgs.map(m => m.message.id));
  const nodes = {};
  const attacks  = [];
  const supports = [];

  for (const m of msgs) {
    const id  = m.message.id;
    const rel = +(m.variables?.public?.relation ?? 0);
    let w = 1;
    if (weightMode === 'impact') {
      const v = m.variables?.public?.votes;
      if (Array.isArray(v)) {
        const total = v.reduce((a, b) => a + b, 0);
        w = total > 0 ? v.reduce((a, b, k) => a + k * b, 0) / total / 4 : 0.5;
      }
    } else if (weightMode === 'votes') {
      const v = m.variables?.public?.votes;
      if (Array.isArray(v)) w = v.reduce((a, b) => a + b, 0) || 1;
    }
    nodes[id] = { id, rel, content: m.message.content, weight: w, original: m.message.original };
  }

  for (const m of msgs) {
    const id  = m.message.id;
    const rel = +(m.variables?.public?.relation ?? 0);
    const pid = m.message.original;
    if (!pid || !ids.has(pid)) continue;

    if (rel === -1)                        attacks.push({ from: id, to: pid, weight: nodes[id]?.weight ?? 1 });
    else if (rel === 1 && proRole === 'support') supports.push({ from: id, to: pid, weight: nodes[id]?.weight ?? 1 });
  }

  return { nodes, attacks, supports };
}

/** Translate support edges into meta-attacks */
function buildMetaAttacks(attacks, supports) {
  const extra = [];
  for (const sup of supports)
    for (const att of attacks)
      if (att.to === sup.to) extra.push({ from: sup.from, to: att.from, weight: sup.weight });
  return [...attacks, ...extra];
}

function _attackedByMap(ids, allAttacks) {
  const map = {};
  for (const id of ids) map[id] = new Set();
  for (const { from, to } of allAttacks) if (map[to]) map[to].add(from);
  return map;
}

/** Grounded semantics (O(n²) fixed-point) */
function computeGrounded(nodes, attacks, supports, rootsIn) {
  const ids        = Object.keys(nodes);
  const allAttacks = buildMetaAttacks(attacks, supports);
  const attackedBy = _attackedByMap(ids, allAttacks);

  const inSet  = new Set();
  const outSet = new Set();

  if (rootsIn) ids.filter(id => nodes[id].rel === 0).forEach(id => inSet.add(id));

  let changed = true;
  while (changed) {
    changed = false;
    for (const id of ids) {
      if (inSet.has(id) || outSet.has(id)) continue;
      const atts = [...attackedBy[id]];
      if (!atts.length || atts.every(a => outSet.has(a)))  { inSet.add(id);  changed = true; }
      else if (atts.some(a => inSet.has(a)))                { outSet.add(id); changed = true; }
    }
  }

  const status = {};
  for (const id of ids) status[id] = inSet.has(id) ? 'in' : outSet.has(id) ? 'out' : 'undecided';
  return status;
}

/** Preferred semantics (exponential — capped at 20 args) */
function computePreferred(nodes, attacks, supports) {
  const ids        = Object.keys(nodes).map(Number);
  const allAttacks = buildMetaAttacks(attacks, supports);
  const attackedBy = _attackedByMap(ids, allAttacks);

  function isAdmissible(S) {
    const Sset = new Set(S);
    for (const a of S) for (const b of S) if (attackedBy[a]?.has(b)) return false;
    for (const a of S)
      for (const att of [...(attackedBy[a] || [])])
        if (!S.some(d => attackedBy[att]?.has(d))) return false;
    return true;
  }

  const lim = ids.slice(0, 20), n = lim.length;
  const preferred = [];

  for (let mask = (1 << n) - 1; mask >= 0; mask--) {
    const S = lim.filter((_, i) => mask & (1 << i));
    if (!isAdmissible(S)) continue;
    if (!preferred.some(ext => S.every(x => ext.includes(x)))) preferred.push(S);
  }

  const status = {};
  for (const id of ids) {
    if (preferred.every(ext => ext.includes(id)))       status[id] = 'in';
    else if (preferred.every(ext => !ext.includes(id))) status[id] = 'out';
    else status[id] = 'undecided';
  }
  return status;
}

/** Stable semantics (exponential — capped at 20 args) */
function computeStable(nodes, attacks, supports) {
  const ids        = Object.keys(nodes).map(Number);
  const allAttacks = buildMetaAttacks(attacks, supports);
  const attackedBy = _attackedByMap(ids, allAttacks);
  const lim = ids.slice(0, 20), n = lim.length;

  for (let mask = (1 << n) - 1; mask >= 0; mask--) {
    const S    = new Set(lim.filter((_, i) => mask & (1 << i)));
    const notS = lim.filter(x => !S.has(x));
    if ([...S].some(a => [...S].some(b => attackedBy[a]?.has(b)))) continue;
    if (notS.every(a => [...S].some(s => attackedBy[a]?.has(s)))) {
      const status = {};
      for (const id of ids) status[id] = S.has(id) ? 'in' : 'out';
      return status;
    }
  }

  const status = {};
  for (const id of ids) status[id] = 'undecided';
  return status;
}

/** Complete semantics (exponential — capped at 18 args) */
function computeComplete(nodes, attacks, supports) {
  const ids        = Object.keys(nodes).map(Number);
  const allAttacks = buildMetaAttacks(attacks, supports);
  const attackedBy = _attackedByMap(ids, allAttacks);

  function defend(S) {
    const defended = new Set(S);
    for (const id of ids) {
      if (defended.has(id)) continue;
      if ([...(attackedBy[id] || [])].every(a => [...S].some(s => attackedBy[a]?.has(s)))) defended.add(id);
    }
    return [...defended];
  }

  function isComplete(S) {
    const Sset = new Set(S);
    if ([...Sset].some(a => [...Sset].some(b => attackedBy[a]?.has(b)))) return false;
    const defended = new Set(defend(S));
    return S.every(x => defended.has(x)) && [...defended].every(x => Sset.has(x));
  }

  const lim = ids.slice(0, 18), n = lim.length;
  const complete = [];
  for (let mask = 0; mask < (1 << n); mask++) {
    const S = lim.filter((_, i) => mask & (1 << i));
    if (isComplete(S)) complete.push(S);
  }

  const status = {};
  for (const id of ids) {
    if (!complete.length)                                    status[id] = 'undecided';
    else if (complete.every(ext => ext.includes(id)))        status[id] = 'in';
    else if (complete.every(ext => !ext.includes(id)))       status[id] = 'out';
    else                                                     status[id] = 'undecided';
  }
  return status;
}

/**
 * Run the selected semantics.
 * @param {string} semantics  'grounded' | 'preferred' | 'stable' | 'complete'
 */
function runSemantics(semantics, nodes, attacks, supports, rootsIn) {
  switch (semantics) {
    case 'grounded':  return computeGrounded(nodes, attacks, supports, rootsIn);
    case 'preferred': return computePreferred(nodes, attacks, supports);
    case 'stable':    return computeStable(nodes, attacks, supports);
    default:          return computeComplete(nodes, attacks, supports);
  }
}

/** Compute which side is winning given the status map */
function computeWinner(nodes, status) {
  let proScore = 0, conScore = 0;
  for (const [id, node] of Object.entries(nodes)) {
    if (node.rel === 0) proScore += node.weight;  // roots count as PRO
    if (status[id] !== 'in') continue;
    if (node.rel ===  1) proScore += node.weight;
    if (node.rel === -1) conScore += node.weight;
  }
  return { proScore, conScore };
}
