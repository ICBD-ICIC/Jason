// ── agents.js ─────────────────────────────────────────────────────────────────
// Agent type CRUD operations and the agent editor panel HTML builder.

// ── CRUD ──────────────────────────────────────────────────────────────────────
function addType() {
  const t = {
    id:         ++uid,
    asl:        options.asl_files[0] || '',
    arch_class: options.arch_classes[0] || '',
    bb_class:   '',
    columns:    [],
    instances:  [],
  };
  types.push(t);
  renderSidebar();
  selectType(t.id);
}

function deleteType(id, e) {
  e.stopPropagation();
  types = types.filter(t => t.id !== id);
  if (activeTypeId === id) activeTypeId = types.length ? types[types.length - 1].id : null;
  renderSidebar();
  renderMain();
}

function setTypeField(id, key, val) {
  const t = types.find(t => t.id === id);
  if (t) { t[key] = val; renderSidebar(); }
}

// ── Instance row helpers ──────────────────────────────────────────────────────
function setCellVal(typeId, ri, col, val) {
  const t = types.find(t => t.id === typeId);
  if (t?.instances[ri]) t.instances[ri][col] = val;
}

function addRow(typeId) {
  const t = types.find(t => t.id === typeId);
  if (!t) return;
  const row = {};
  t.columns.forEach(c => row[c] = '');
  t.instances.push(row);
  renderMain();
  renderSidebar();
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
  document.getElementById('col-name-input').value = '';
  document.getElementById('col-modal').classList.add('open');
  setTimeout(() => document.getElementById('col-name-input').focus(), 60);
}

function confirmAddCol() {
  const name = document.getElementById('col-name-input').value.trim();
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
  const col = t.columns[ci];
  t.columns.splice(ci, 1);
  t.instances.forEach(inst => delete inst[col]);
  renderMain();
}

// ── CSV upload ────────────────────────────────────────────────────────────────
async function loadAgentCsv(typeId, input) {
  const file = input.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const r    = await fetch('/api/parse_csv', { method: 'POST', body: fd });
    const data = await r.json();
    if (data.error) { showToast(data.error); return; }
    const t = types.find(t => t.id === typeId);
    if (!t) return;
    data.columns.forEach(c => { if (!t.columns.includes(c)) t.columns.push(c); });
    data.rows.forEach(row => {
      const inst = {};
      t.columns.forEach(c => inst[c] = (row[c] ?? ''));
      t.instances.push(inst);
    });
    renderMain();
    renderSidebar();
  } catch (e) { showToast('Failed to parse CSV: ' + e.message); }
  input.value = '';
}

// ── ASL preview ───────────────────────────────────────────────────────────────
async function togglePreview(typeId) {
  const wrap = document.getElementById(`asl-wrap-${typeId}`);
  if (!wrap) return;
  if (wrap.style.display === 'block') { wrap.style.display = 'none'; return; }
  await refreshPreview(typeId);
  wrap.style.display = 'block';
}

async function refreshPreview(typeId) {
  const t = types.find(t => t.id === typeId);
  if (!t?.asl) return;
  try {
    const r    = await fetch('/api/asl_preview?name=' + encodeURIComponent(t.asl));
    const data = await r.json();
    const code = document.getElementById(`asl-code-${typeId}`);
    const bar  = document.getElementById(`asl-bar-${typeId}`);
    if (code) code.textContent = data.content || data.error || '';
    if (bar)  bar.textContent  = `preview — ${t.asl}`;
  } catch {}
}

// ── HTML builders ─────────────────────────────────────────────────────────────
function buildAgentEditor(t) {
  const aslOpts  = options.asl_files.map(f =>
    `<option value="${f}"${f === t.asl ? ' selected' : ''}>${f}</option>`).join('');

  const archOpts = `<option value=""${!t.arch_class ? ' selected' : ''}>(none)</option>`
    + options.arch_classes.map(c =>
        `<option value="${c}"${c === t.arch_class ? ' selected' : ''}>${c}</option>`).join('');

  const bbOpts = `<option value=""${!t.bb_class ? ' selected' : ''}>(none)</option>`
    + options.bb_classes.map(c =>
        `<option value="${c}"${c === t.bb_class ? ' selected' : ''}>${c}</option>`).join('');

  return `
    <div class="editor">
      <div class="ed-header">
        <div class="tag">type #${types.indexOf(t) + 1}</div>
        <div>
          <h2>${t.asl || 'New Agent Type'}
            <small>Configure .asl, architecture, and per-instance facts</small>
          </h2>
        </div>
      </div>

      <!-- Identity card -->
      <div class="card">
        <div class="card-head"><div class="dot"></div><h4>Identity</h4></div>
        <div class="card-body">
          <div class="grid-2">
            <div class="field">
              <label>Base .asl File</label>
              <select onchange="setTypeField(${t.id},'asl',this.value);refreshPreview(${t.id})">${aslOpts}</select>
            </div>
          </div>
          <div class="asl-wrap" id="asl-wrap-${t.id}">
            <div class="asl-bar" id="asl-bar-${t.id}">preview — ${t.asl}</div>
            <pre class="asl-code" id="asl-code-${t.id}"></pre>
          </div>
          <div style="margin-top:10px">
            <button class="btn-sm" onclick="togglePreview(${t.id})">👁 Toggle .asl preview</button>
          </div>
        </div>
      </div>

      <!-- Architecture card -->
      <div class="card">
        <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Architecture</h4></div>
        <div class="card-body grid-2">
          <div class="field">
            <label>agentArchClass</label>
            <select onchange="setTypeField(${t.id},'arch_class',this.value)">${archOpts}</select>
          </div>
          <div class="field">
            <label>beliefBaseClass</label>
            <select onchange="setTypeField(${t.id},'bb_class',this.value)">${bbOpts}</select>
          </div>
        </div>
      </div>

      <!-- Instances card -->
      <div class="card">
        <div class="card-head">
          <div class="dot" style="background:#f0a500"></div>
          <h4>Instances — ${t.instances.length} agent${t.instances.length !== 1 ? 's' : ''}</h4>
          <div class="card-head-actions">
            <button class="btn-sm" onclick="openAddCol(${t.id})">+ Column</button>
          </div>
        </div>
        <div class="card-body">
          <div class="csv-zone">
            <input type="file" accept=".csv" onchange="loadAgentCsv(${t.id},this)">
            Drop wide CSV or click — <em>columns = attributes, rows = agents</em>
          </div>
          ${buildInstancesTable(t)}
          <div class="table-toolbar">
            <button class="btn-sm accent" onclick="addRow(${t.id})">+ Add Instance</button>
            ${t.instances.length > 0
              ? `<button class="btn-sm" onclick="clearRows(${t.id})">Clear All</button>`
              : ''}
          </div>
        </div>
      </div>
    </div>`;
}

function buildInstancesTable(t) {
  if (!t.columns.length && !t.instances.length)
    return `<div class="no-rows">Upload a CSV or add columns, then add instances</div>`;

  const colHeaders = t.columns.map((c, ci) => `
    <th>${c}
      <button class="btn-del-row" style="margin-left:3px;font-size:.6rem"
        onclick="deleteCol(${t.id},${ci})" title="Remove column">✕</button>
    </th>`).join('');

  const rows = t.instances.map((inst, ri) => {
    const cells = t.columns.map(c => `
      <td><input type="text" value="${esc(inst[c] ?? '')}" placeholder="—"
        oninput="setCellVal(${t.id},${ri},'${c}',this.value)"></td>`).join('');
    return `<tr>
      <td class="td-idx">${ri + 1}</td>
      ${cells}
      <td><button class="btn-del-row" onclick="deleteRow(${t.id},${ri})">✕</button></td>
    </tr>`;
  }).join('') || (t.columns.length
    ? `<tr><td colspan="${t.columns.length + 2}" class="no-rows">No instances yet</td></tr>`
    : '');

  return `
    <div class="tbl-wrap">
      <table class="data-table">
        <thead><tr><th class="col-idx">#</th>${colHeaders}<th class="col-del"></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}