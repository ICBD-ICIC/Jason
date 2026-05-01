// agents.js — agent type CRUD + editor HTML

// ── CRUD ──────────────────────────────────────────────────────────────────────

function addType() {
  const t = { id: ++uid, asl: options.asl_files[0] || '', arch_class: options.arch_classes[0] || '', bb_class: '', columns: [], instances: [] };
  types.push(t);
  renderSidebar();
  selectType(t.id);
}

/** Total agent count across all instance rows (respecting _count) */
function totalInstances(t) {
  return t.instances.reduce((s, inst) => s + (parseInt(inst._count) || 1), 0);
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

function setCountVal(typeId, ri, val) {
  const t = types.find(t => t.id === typeId);
  if (!t?.instances[ri]) return;
  const n = parseInt(val);
  t.instances[ri]._count = (isNaN(n) || n < 1) ? 1 : n;
  renderSidebar(); // update pill count
}

function addRow(typeId, count) {
  const t = types.find(t => t.id === typeId); if (!t) return;
  const n = Math.max(1, parseInt(count) || 1);
  for (let i = 0; i < n; i++) {
    const inst = Object.fromEntries(t.columns.map(c => [c, '']));
    inst._count = 1;
    t.instances.push(inst);
  }
  renderMain();
  renderSidebar();
  setTimeout(() => initAgentVirtScroll(typeId), 0);
}

function deleteRow(typeId, ri) {
  const t = types.find(t => t.id === typeId); if (!t) return;
  t.instances.splice(ri, 1);
  renderMain();
  renderSidebar();
  setTimeout(() => initAgentVirtScroll(typeId), 0);
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

    const userCols = data.columns.filter(c => c !== '_count');
    userCols.forEach(c => { if (!t.columns.includes(c)) t.columns.push(c); });

    // Push rows in chunks to avoid blocking the main thread
    const CHUNK = 2000;
    const push = async (i) => {
      const slice = data.rows.slice(i, i + CHUNK);
      for (const row of slice) {
        const inst = Object.fromEntries(t.columns.map(c => [c, row[c] ?? '']));
        inst._count = parseInt(row._count) || 1;
        t.instances.push(inst);
      }
      renderSidebar();
      if (i + CHUNK < data.rows.length) {
        await new Promise(r => setTimeout(r, 0)); // yield to browser
        return push(i + CHUNK);
      }
      renderMain(); // only re-render fully once done
    };

    await push(0);
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
  const total = totalInstances(t);
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
          <h4>Instance Groups — ${t.instances.length} row${t.instances.length !== 1 ? 's' : ''}, <span style="color:var(--accent2)">${total} agent${total !== 1 ? 's' : ''} total</span></h4>
          <div class="card-head-actions">
            <button class="btn-sm" onclick="openAddCol(${t.id})">+ Column</button>
          </div>
        </div>
        <div class="table-toolbar">
          <button class="btn-sm accent" onclick="addRow(${t.id}, $('#add-count-${t.id}').value)">+ Add Row</button>
          <label class="add-count-label" title="Number of rows to add">
            <span class="add-count-prefix">×</span>
            <input type="number" id="add-count-${t.id}" class="add-count-input" value="1" min="1" max="1000"
              onkeydown="if(event.key==='Enter') addRow(${t.id}, this.value)">
          </label>
          ${t.instances.length ? `<button class="btn-sm btn-clear" onclick="clearRows(${t.id})">Clear All</button>` : ''}
        </div>
        <div class="card-body">
          <div class="csv-zone">
            <input type="file" accept=".csv" onchange="loadAgentCsv(${t.id},this)">
            Drop CSV or click — <em>columns = attributes, rows = groups · optional <code>_count</code> column</em>
          </div>
          ${buildInstancesTable(t)}
        </div>
      </div>
    </div>`;
}

// ── Virtual scroll constants ──────────────────────────────────────────────────
const AGENT_VIRT_ROW_H  = 38;
const AGENT_VIRT_OVERSC = 8;

function buildInstancesTable(t) {
  if (!t.columns.length && !t.instances.length)
    return `<div class="no-rows">No instance groups yet — click <strong>+ Add Row</strong> or upload a CSV</div>`;

  if (!t.instances.length) {
    return `<div class="tbl-wrap"><table class="data-table">
      <thead><tr><th class="col-idx">#</th><th title="Number of agents in this group" style="width:90px">× Count</th><th></th><th class="col-del"></th></tr></thead>
      <tbody><tr><td colspan="4" class="no-rows">No instance groups yet</td></tr></tbody>
    </table></div>`;
  }

  const colHeaders = t.columns.map((c, ci) =>
    `<th>${esc(c)}<button class="btn-del-col" onclick="deleteCol(${t.id},${ci})" title="Remove">✕</button></th>`
  ).join('');
  const colCount = t.columns.length + 3; // idx + count + cols + del

  const h = Math.max(120, Math.min(480, t.instances.length * AGENT_VIRT_ROW_H + 44));

  return `
    <div class="virt-scroll-wrap" id="agent-virt-wrap-${t.id}"
         style="height:${h}px;overflow-y:auto;"
         onscroll="onAgentVirtScroll(${t.id})">
      <table class="data-table" style="width:100%;table-layout:fixed;">
        <thead style="position:sticky;top:0;z-index:2;background:var(--card);">
          <tr>
            <th class="col-idx" style="width:44px">#</th>
            <th style="width:90px">× Count</th>
            ${colHeaders}
            <th class="col-del" style="width:36px"></th>
          </tr>
        </thead>
      </table>
      <div style="position:relative;height:${t.instances.length * AGENT_VIRT_ROW_H}px;">
        <table class="data-table" id="agent-virt-table-${t.id}"
               style="width:100%;table-layout:fixed;position:absolute;top:0;left:0;">
          <tbody id="agent-virt-tbody-${t.id}"></tbody>
        </table>
      </div>
    </div>`;
}

function onAgentVirtScroll(typeId) {
  const wrap = $(`#agent-virt-wrap-${typeId}`);
  if (wrap) renderAgentVirtRows(typeId, wrap.scrollTop);
}

function renderAgentVirtRows(typeId, scrollTop = 0) {
  const tbody = $(`#agent-virt-tbody-${typeId}`);
  const table = $(`#agent-virt-table-${typeId}`);
  const wrap  = $(`#agent-virt-wrap-${typeId}`);
  if (!tbody || !table || !wrap) return;

  const t = types.find(t => t.id === typeId); if (!t) return;
  const total = t.instances.length;
  const viewH = wrap.clientHeight;

  const first = Math.floor(scrollTop / AGENT_VIRT_ROW_H);
  const start = Math.max(0, first - AGENT_VIRT_OVERSC);
  const end   = Math.min(total - 1, first + Math.ceil(viewH / AGENT_VIRT_ROW_H) + AGENT_VIRT_OVERSC);

  table.style.top = (start * AGENT_VIRT_ROW_H) + 'px';

  const inputSt = `style="background:var(--surface);border:1px solid var(--border);border-radius:4px;font-family:var(--mono);font-size:.8rem;padding:4px 7px;width:100%;"`;
  const rows = [];
  for (let ri = start; ri <= end; ri++) {
    const inst = t.instances[ri];
    const cells = t.columns.map(c =>
      `<td><input type="text" value="${esc(inst[c] ?? '')}" placeholder="—" ${inputSt}
        oninput="setCellVal(${typeId},${ri},'${esc(c)}',this.value)"></td>`
    ).join('');
    rows.push(`<tr style="height:${AGENT_VIRT_ROW_H}px">
      <td class="td-idx">${ri + 1}</td>
      <td>${buildCountInput(typeId, ri, inst._count)}</td>
      ${cells}
      <td><button class="btn-del-row" onclick="deleteRow(${typeId},${ri})">✕</button></td>
    </tr>`);
  }
  tbody.innerHTML = rows.join('');
}

function initAgentVirtScroll(typeId) {
  renderAgentVirtRows(typeId, 0);
}

function buildCountInput(typeId, ri, count) {
  const val = parseInt(count) || 1;
  const highlight = val > 1 ? 'style="color:var(--accent2);font-weight:600;border-color:rgba(61,255,208,.3);"' : '';
  return `<input type="number" value="${val}" min="1"
    title="Number of agents in this group"
    ${highlight}
    oninput="setCountVal(${typeId},${ri},this.value)"
    style="background:var(--surface);border:1px solid var(--border);border-radius:4px;
           font-family:var(--mono);font-size:.8rem;padding:4px 7px;width:80px;
           -moz-appearance:textfield;"
    onchange="this.style.color=parseInt(this.value)>1?'var(--accent2)':'';
              this.style.borderColor=parseInt(this.value)>1?'rgba(61,255,208,.3)':'';">`;
}
