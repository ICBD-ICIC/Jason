// initializers.js — generic initializer editor (messages.csv, public_profiles.csv)

// ── Virtual scroll constants (shared with network.js style) ───────────────────
const INIT_VIRT_ROW_H  = 34;
const INIT_VIRT_OVERSC = 10;

// Per-initializer virt scroll state (keyed by csv name)
const _initVirtState = {};  // { [name]: { scrollTop: 0 } }

// ── Router ────────────────────────────────────────────────────────────────────

function buildInitEditor(name) {
  if (name === 'network.csv') return buildNetworkEditor(name);
  return buildGenericInitEditor(name);
}

// ── Generic editor (messages.csv, public_profiles.csv, …) ────────────────────

function buildGenericInitEditor(name) {
  const st = initializers[name]; if (!st) return '';
  const { schema, rows } = st;
  const agents     = getAllAgentNames();
  const isProfiles = name === 'public_profiles.csv';

  if (!_initVirtState[name]) _initVirtState[name] = { scrollTop: 0 };

  const agentBanner = isProfiles ? `
    <div class="agent-source-info">
      ${agents.length
        ? `<div class="agent-source-box">
            <div><strong>${agents.length}</strong> agent${agents.length !== 1 ? 's' : ''} detected from defined types</div>
            <div class="agent-chips">${agents.map(n => `<span class="agent-chip">${esc(n)}</span>`).join('')}</div>
           </div>`
        : `<div>No agent instances yet — <strong>add types with instances</strong> to see agent names here.</div>`
      }
    </div>` : '';

  return `
    <div class="editor">
      <div class="ed-header">
        <div class="tag blue">initializer</div>
        <h2>${esc(name)}<small>Edit rows · written to initializer/${esc(name)} on generate</small></h2>
      </div>
      ${agentBanner}
      <div class="card">
        <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Load from file</h4></div>
        <div class="card-body">
          <div class="csv-zone">
            <input type="file" accept=".csv" onchange="loadInitCsvUpload('${name}',this)">
            Upload a CSV file to replace current rows
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-head">
          <div class="dot" style="background:#f0a500"></div>
          <h4>Rows — <span id="init-row-count-${_safeId(name)}">${rows.length}</span> entr${rows.length !== 1 ? 'ies' : 'y'}</h4>
          <div class="card-head-actions">
            ${rows.length ? `<button class="btn-sm btn-clear" onclick="clearInitRows('${name}')">Clear All</button>` : ''}
          </div>
        </div>
        <div class="table-toolbar">
          <button class="btn-sm accent" onclick="addInitRow('${name}')">+ Add Row</button>
        </div>
        <div class="card-body">
          ${buildGenericVirtTable(name, st)}
        </div>
      </div>
    </div>`;
}

// ── Virtual table builder ─────────────────────────────────────────────────────

function _safeId(name) {
  // Turn "public_profiles.csv" → "public_profiles_csv" for use in element IDs
  return name.replace(/[^a-z0-9]/gi, '_');
}

function buildGenericVirtTable(name, st) {
  const { schema, rows } = st;
  const sid = _safeId(name);

  if (!rows.length) {
    return `
      <div class="tbl-wrap">
        <table class="data-table">
          <thead><tr>
            <th class="col-idx">#</th>
            ${schema.map(c => `<th>${esc(c)}</th>`).join('')}
            <th class="col-del"></th>
          </tr></thead>
          <tbody>
            <tr><td colspan="${schema.length + 2}" class="no-rows">No rows yet — upload a file or click + Add Row</td></tr>
          </tbody>
        </table>
      </div>`;
  }

  const colWidths = _initColWidths(name);
  const colgroupCols = ['44px', ...colWidths, '36px'].map(w => `<col style="width:${w}">`).join('');
  const thCells = schema.map(c => `<th>${esc(c)}</th>`).join('');

  const h = Math.max(120, Math.min(520, rows.length * INIT_VIRT_ROW_H + 44));

  return `
    <div class="virt-scroll-wrap"
         id="init-virt-wrap-${sid}"
         style="height:${h}px; overflow-y:auto;"
         onscroll="onInitVirtScroll('${name}')">
      <table class="data-table" style="width:100%;table-layout:fixed;">
        <colgroup>${colgroupCols}</colgroup>
        <thead style="position:sticky;top:0;z-index:2;background:var(--card);">
          <tr>
            <th class="col-idx">#</th>
            ${thCells}
            <th class="col-del"></th>
          </tr>
        </thead>
      </table>
      <div style="position:relative;height:${rows.length * INIT_VIRT_ROW_H}px;">
        <table class="data-table"
               id="init-virt-table-${sid}"
               style="width:100%;table-layout:fixed;position:absolute;top:0;left:0;">
          <colgroup>${colgroupCols}</colgroup>
          <tbody id="init-virt-tbody-${sid}"></tbody>
        </table>
      </div>
    </div>`;
}

// Column widths per initializer — lets us give 'agent' a narrower col, 'content' a wider one
function _initColWidths(name) {
  if (name === 'public_profiles.csv') return ['160px', '160px', '1fr'];
  if (name === 'messages.csv')        return ['60px', '120px', '1fr', '120px', '60px', '120px', '160px'];
  // fallback: equal distribution
  const schema = initializers[name]?.schema || [];
  return schema.map(() => '1fr');
}

// ── Virtual scroll render ─────────────────────────────────────────────────────

function onInitVirtScroll(name) {
  const sid  = _safeId(name);
  const wrap = document.getElementById(`init-virt-wrap-${sid}`);
  if (!wrap) return;
  _initVirtState[name] = _initVirtState[name] || {};
  _initVirtState[name].scrollTop = wrap.scrollTop;
  renderInitVirtRows(name, wrap.scrollTop);
}

function initInitVirtScroll(name) {
  const saved = _initVirtState[name]?.scrollTop ?? 0;
  const sid   = _safeId(name);
  const wrap  = document.getElementById(`init-virt-wrap-${sid}`);
  if (wrap && saved) wrap.scrollTop = saved;
  renderInitVirtRows(name, saved);
}

function renderInitVirtRows(name, scrollTop = 0) {
  const sid   = _safeId(name);
  const tbody = document.getElementById(`init-virt-tbody-${sid}`);
  const table = document.getElementById(`init-virt-table-${sid}`);
  const wrap  = document.getElementById(`init-virt-wrap-${sid}`);
  if (!tbody || !table || !wrap) return;

  const st     = initializers[name]; if (!st) return;
  const { schema, rows } = st;
  const total  = rows.length;
  const viewH  = wrap.clientHeight;

  const first = Math.floor(scrollTop / INIT_VIRT_ROW_H);
  const start = Math.max(0, first - INIT_VIRT_OVERSC);
  const end   = Math.min(total - 1, first + Math.ceil(viewH / INIT_VIRT_ROW_H) + INIT_VIRT_OVERSC);

  table.style.top = (start * INIT_VIRT_ROW_H) + 'px';

  const isProfiles = name === 'public_profiles.csv';
  const agents     = isProfiles ? getAllAgentNames() : [];
  const listId     = `init-agent-list-${sid}`;

  // Build a shared <datalist> for agent autocomplete (profiles only)
  const datalist = (isProfiles && agents.length)
    ? `<datalist id="${listId}">${agents.map(n => `<option value="${esc(n)}">`).join('')}</datalist>`
    : '';

  const inputSt = `style="background:var(--surface);border:1px solid var(--border);border-radius:4px;font-family:var(--mono);font-size:.78rem;padding:4px 7px;width:100%;"`;

  const htmlRows = [];
  for (let ri = start; ri <= end; ri++) {
    const row = rows[ri];
    const cells = schema.map(col => {
      const val = row[col] ?? '';
      // First column of public_profiles is 'agent' — show autocomplete
      const listAttr = (isProfiles && col === 'agent' && agents.length)
        ? `list="${listId}"`
        : '';
      return `<td><input type="text" value="${esc(val)}" placeholder="—" ${listAttr} ${inputSt}
        oninput="setInitCell('${name}',${ri},'${col}',this.value)"></td>`;
    }).join('');

    htmlRows.push(`<tr style="height:${INIT_VIRT_ROW_H}px">
      <td class="td-idx">${ri + 1}</td>
      ${cells}
      <td><button class="btn-del-row" onclick="deleteInitRow('${name}',${ri})">✕</button></td>
    </tr>`);
  }

  tbody.innerHTML = datalist + htmlRows.join('');
}

// ── Row counter helper (avoids full re-render just to update count) ───────────
function _updateInitRowCount(name) {
  const sid = _safeId(name);
  const el  = document.getElementById(`init-row-count-${sid}`);
  if (el) el.textContent = initializers[name]?.rows.length ?? 0;
}

// ── Virtual spacer height helper (keeps scroll area correct after mutations) ──
function _resizeInitVirtSpace(name) {
  const sid  = _safeId(name);
  const wrap = document.getElementById(`init-virt-wrap-${sid}`);
  if (!wrap) return;
  const rows = initializers[name]?.rows.length ?? 0;
  // The spacer div is the second child of the wrap
  const spacer = wrap.querySelector('div[style*="position:relative"]');
  if (spacer) spacer.style.height = (rows * INIT_VIRT_ROW_H) + 'px';
  // Also resize the outer wrap height (capped at 520px)
  wrap.style.height = Math.max(120, Math.min(520, rows * INIT_VIRT_ROW_H + 44)) + 'px';
}

// ── Mutations ─────────────────────────────────────────────────────────────────

function setInitCell(name, ri, col, val) {
  if (initializers[name]?.rows[ri]) {
    initializers[name].rows[ri][col] = val;
    if (name === 'network.csv') setTimeout(drawNetPreview, 100);
  }
}

function addInitRow(name) {
  const st = initializers[name]; if (!st) return;
  st.rows.push(Object.fromEntries(st.schema.map(c => [c, ''])));

  // If the virt table exists, update in-place without a full re-render
  const sid  = _safeId(name);
  const wrap = document.getElementById(`init-virt-wrap-${sid}`);
  if (wrap) {
    _resizeInitVirtSpace(name);
    _updateInitRowCount(name);
    // Scroll to bottom so the new row is visible, then render
    wrap.scrollTop = wrap.scrollHeight;
    renderInitVirtRows(name, wrap.scrollTop);
    renderInitNav();
  } else {
    // First row — need full render to build the table skeleton
    renderMain();
    renderInitNav();
    setTimeout(() => initInitVirtScroll(name), 0);
  }
}

function deleteInitRow(name, ri) {
  const st = initializers[name]; if (!st) return;
  st.rows.splice(ri, 1);

  const sid  = _safeId(name);
  const wrap = document.getElementById(`init-virt-wrap-${sid}`);
  if (wrap) {
    if (!st.rows.length) {
      // Last row gone — rebuild skeleton to show "no rows" message
      renderMain();
      renderInitNav();
    } else {
      _resizeInitVirtSpace(name);
      _updateInitRowCount(name);
      renderInitVirtRows(name, wrap.scrollTop);
      renderInitNav();
    }
  } else {
    renderMain(); renderInitNav();
  }

  if (name === 'network.csv') setTimeout(() => { drawNetPreview(); initNetVirtScroll(); }, 80);
}

function clearInitRows(name) {
  if (!initializers[name]) return;
  initializers[name].rows = [];
  renderMain(); renderInitNav();
  if (name === 'network.csv') setTimeout(() => { drawNetPreview(); initNetVirtScroll(); }, 80);
}

async function loadInitCsvUpload(name, input) {
  const file = input.files[0]; if (!file) return;
  const fd = new FormData(); fd.append('file', file); fd.append('name', name);
  try {
    const data = await fetch('/api/parse_initializer_csv', { method: 'POST', body: fd }).then(r => r.json());
    if (data.error) { showToast(data.error); return; }

    // Clear first, render empty shell immediately so UI isn't stuck
    initializers[name].rows = [];
    renderMain();
    renderInitNav();

    // Push rows in chunks, yielding between each to keep UI responsive
    const CHUNK = 3000;
    for (let i = 0; i < data.rows.length; i += CHUNK) {
      initializers[name].rows.push(...data.rows.slice(i, i + CHUNK));

      // Update virt scroll state in-place when the table skeleton already exists
      const sid  = _safeId(name);
      const wrap = document.getElementById(`init-virt-wrap-${sid}`);
      if (wrap) {
        _resizeInitVirtSpace(name);
        _updateInitRowCount(name);
        renderInitVirtRows(name, wrap.scrollTop);
      }
      renderInitNav();
      await new Promise(r => setTimeout(r, 0)); // yield to browser
    }

    // Final render (rebuilds the outer skeleton with correct final height)
    renderMain();
    renderInitNav();
    setTimeout(() => initInitVirtScroll(name), 0);

    if (name === 'network.csv') {
      setTimeout(() => { _setupResizeHandle(); initNetVirtScroll(); }, 80);
      setTimeout(() => drawNetPreview(), 300);
    }
  } catch (e) { showToast('Failed to parse CSV: ' + e.message); }
  input.value = '';
}