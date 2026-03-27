// agents.js — agent type CRUD + editor HTML

// ── CRUD ──────────────────────────────────────────────────────────────────────

function addType() {
  const t = { id: ++uid, asl: options.asl_files[0] || '', arch_class: options.arch_classes[0] || '', bb_class: '', columns: [], instances: [] };
  types.push(t);
  renderSidebar();
  selectType(t.id);
}

function deleteType(id, e) {
  e.stopPropagation();
  types = types.filter(t => t.id !== id);
  if (activeTypeId === id) activeTypeId = types.at(-1)?.id ?? null;
  renderSidebar(); renderMain();
}

function setTypeField(id, key, val) {
  const t = types.find(t => t.id === id);
  if (t) { t[key] = val; renderSidebar(); }
}

// ── Instance helpers ──────────────────────────────────────────────────────────

function setCellVal(typeId, ri, col, val) {
  const t = types.find(t => t.id === typeId);
  if (t?.instances[ri]) t.instances[ri][col] = val;
}

function addRow(typeId, count) {
  const t = types.find(t => t.id === typeId);
  if (!t) return;
  const n = Math.max(1, parseInt(count) || 1);
  for (let i = 0; i < n; i++) t.instances.push(Object.fromEntries(t.columns.map(c => [c, ''])));
  renderMain(); renderSidebar();
}

function deleteRow(typeId, ri) {
  const t = types.find(t => t.id === typeId);
  if (t) { t.instances.splice(ri, 1); renderMain(); renderSidebar(); }
}

function clearRows(typeId) {
  const t = types.find(t => t.id === typeId);
  if (t) { t.instances = []; renderMain(); renderSidebar(); }
}

// ── Column helpers ────────────────────────────────────────────────────────────

function openAddCol(typeId) {
  pendingColTypeId = typeId;
  $('#col-name-input').value = '';
  $('#col-modal').classList.add('open');
  setTimeout(() => $('#col-name-input').focus(), 60);
}

function confirmAddCol() {
  const name = $('#col-name-input').value.trim();
  if (!name) return;
  const t = types.find(t => t.id === pendingColTypeId);
  if (t && !t.columns.includes(name)) {
    t.columns.push(name);
    t.instances.forEach(inst => { if (!(name in inst)) inst[name] = ''; });
    renderMain();
  }
  closeModal('col-modal');
}

function deleteCol(typeId, ci) {
  const t = types.find(t => t.id === typeId);
  if (!t) return;
  const col = t.columns.splice(ci, 1)[0];
  t.instances.forEach(inst => delete inst[col]);
  renderMain();
}

// ── CSV upload ────────────────────────────────────────────────────────────────

async function loadAgentCsv(typeId, input) {
  const file = input.files[0]; if (!file) return;
  const fd = new FormData(); fd.append('file', file);
  try {
    const data = await fetch('/api/parse_csv', { method: 'POST', body: fd }).then(r => r.json());
    if (data.error) { showToast(data.error); return; }
    const t = types.find(t => t.id === typeId); if (!t) return;
    data.columns.forEach(c => { if (!t.columns.includes(c)) t.columns.push(c); });
    data.rows.forEach(row => t.instances.push(Object.fromEntries(t.columns.map(c => [c, row[c] ?? '']))));
    renderMain(); renderSidebar();
  } catch (e) { showToast('Failed to parse CSV: ' + e.message); }
  input.value = '';
}

// ── ASL preview ───────────────────────────────────────────────────────────────

async function togglePreview(typeId) {
  const wrap = $(`#asl-wrap-${typeId}`); if (!wrap) return;
  if (wrap.style.display === 'block') { wrap.style.display = 'none'; return; }
  await refreshPreview(typeId);
  wrap.style.display = 'block';
}

async function refreshPreview(typeId) {
  const t = types.find(t => t.id === typeId); if (!t?.asl) return;
  try {
    const data = await fetch(`/api/asl_preview?name=${encodeURIComponent(t.asl)}`).then(r => r.json());
    const code = $(`#asl-code-${typeId}`), bar = $(`#asl-bar-${typeId}`);
    if (code) code.textContent = data.content || data.error || '';
    if (bar)  bar.textContent  = `preview — ${t.asl}`;
  } catch {}
}

// ── HTML builders ─────────────────────────────────────────────────────────────

function buildAgentEditor(t) {
  return `
    <div class="editor">
      <div class="ed-header">
        <div class="tag">type #${types.indexOf(t) + 1}</div>
        <h2>${esc(t.asl || 'New Agent Type')}
          <small>Configure .asl, architecture, and per-instance facts</small>
        </h2>
      </div>

      <div class="card">
        <div class="card-head"><div class="dot"></div><h4>Identity</h4></div>
        <div class="card-body">
          <div class="field" style="max-width:340px">
            <label>Base .asl File</label>
            <select onchange="setTypeField(${t.id},'asl',this.value);refreshPreview(${t.id})">
              ${optTags(options.asl_files, t.asl)}
            </select>
          </div>
          <div class="asl-wrap" id="asl-wrap-${t.id}">
            <div class="asl-bar" id="asl-bar-${t.id}">preview — ${esc(t.asl)}</div>
            <pre class="asl-code" id="asl-code-${t.id}"></pre>
          </div>
          <div class="asl-toggle-btn">
            <button class="btn-sm" onclick="togglePreview(${t.id})">👁 Toggle .asl preview</button>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Architecture</h4></div>
        <div class="card-body grid-2">
          <div class="field">
            <label>agentArchClass</label>
            <select onchange="setTypeField(${t.id},'arch_class',this.value)">
              ${optTags(options.arch_classes, t.arch_class, '(none)')}
            </select>
          </div>
          <div class="field">
            <label>beliefBaseClass</label>
            <select onchange="setTypeField(${t.id},'bb_class',this.value)">
              ${optTags(options.bb_classes, t.bb_class, '(none)')}
            </select>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div class="dot" style="background:#f0a500"></div>
          <h4>Instances — ${t.instances.length} agent${t.instances.length !== 1 ? 's' : ''}</h4>
          <div class="card-head-actions">
            <button class="btn-sm" onclick="openAddCol(${t.id})">+ Column</button>
          </div>
        </div>
        <div class="table-toolbar">
          <button class="btn-sm accent" onclick="addRow(${t.id}, $('#add-count-${t.id}').value)">+ Add Instance</button>
          <label class="add-count-label" title="Number of instances to add">
            <span class="add-count-prefix">×</span>
            <input type="number" id="add-count-${t.id}" class="add-count-input" value="1" min="1" max="1000"
              onkeydown="if(event.key==='Enter') addRow(${t.id}, this.value)">
          </label>
          ${t.instances.length ? `<button class="btn-sm btn-clear" onclick="clearRows(${t.id})">Clear All</button>` : ''}
        </div>
        <div class="card-body">
          <div class="csv-zone">
            <input type="file" accept=".csv" onchange="loadAgentCsv(${t.id},this)">
            Drop CSV or click — <em>columns = attributes, rows = agents</em>
          </div>
          ${buildInstancesTable(t)}
        </div>
      </div>
    </div>`;
}

function buildInstancesTable(t) {
  if (!t.columns.length && !t.instances.length)
    return `<div class="no-rows">No instances yet — click <strong>+ Add Instance</strong> or upload a CSV</div>`;

  // Instances with no columns
  if (!t.columns.length) {
    return `<div class="tbl-wrap"><table class="data-table">
      <thead><tr><th class="col-idx">#</th><th></th><th class="col-del"></th></tr></thead>
      <tbody>${t.instances.map((_, ri) => `
        <tr>
          <td class="td-idx">${ri + 1}</td>
          <td><span class="no-attr-msg">No attributes — use <strong>+ Column</strong> to define some.</span></td>
          <td><button class="btn-del-row" onclick="deleteRow(${t.id},${ri})">✕</button></td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
  }

  const headers = t.columns.map((c, ci) =>
    `<th>${esc(c)}<button class="btn-del-col" onclick="deleteCol(${t.id},${ci})" title="Remove">✕</button></th>`
  ).join('');

  const rows = t.instances.map((inst, ri) =>
    `<tr>
      <td class="td-idx">${ri + 1}</td>
      ${t.columns.map(c => `<td><input type="text" value="${esc(inst[c] ?? '')}" placeholder="—"
        oninput="setCellVal(${t.id},${ri},'${esc(c)}',this.value)"></td>`).join('')}
      <td><button class="btn-del-row" onclick="deleteRow(${t.id},${ri})">✕</button></td>
    </tr>`
  ).join('') || `<tr><td colspan="${t.columns.length + 2}" class="no-rows">No instances yet</td></tr>`;

  return `<div class="tbl-wrap"><table class="data-table">
    <thead><tr><th class="col-idx">#</th>${headers}<th class="col-del"></th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}
