// ── initializers.js ───────────────────────────────────────────────────────────
// Generic initializer editor (messages.csv, public_profiles.csv).
// network.csv gets its own dedicated module (network.js).

// ── Router ────────────────────────────────────────────────────────────────────
function buildInitEditor(name) {
  if (name === 'network.csv') return buildNetworkEditor(name);
  return buildGenericInitEditor(name);
}

// ── Generic editor (any initializer with a fixed schema) ──────────────────────
function buildGenericInitEditor(name) {
  const st     = initializers[name];
  if (!st) return '';
  const schema = st.schema;

  const agentNames = getAllAgentNames();
  const hasAgents  = agentNames.length > 0;

  // Show agent banner only for public_profiles.csv
  let agentBanner = '';
  if (name === 'public_profiles.csv') {
    agentBanner = hasAgents
      ? `<div class="agent-source-info">
          <div class="agent-source-box">
            <div><strong>${agentNames.length}</strong> agent${agentNames.length !== 1 ? 's' : ''} detected from defined types</div>
            <div class="agent-chips">${agentNames.map(n => `<span class="agent-chip">${esc(n)}</span>`).join('')}</div>
          </div>
        </div>`
      : `<div class="agent-source-info">
          <div>No agent instances yet —
            <strong>add types with instances</strong> to see agent names here.
          </div>
        </div>`;
  }

  const colHeaders = schema.map(c => `<th>${c}</th>`).join('');

  const rows = st.rows.map((row, ri) => {
    const cells = schema.map(c => `
      <td><input type="text" value="${esc(row[c] ?? '')}" placeholder=""
        oninput="setInitCell('${name}',${ri},'${c}',this.value)"></td>`).join('');
    return `<tr>
      <td class="td-idx">${ri + 1}</td>
      ${cells}
      <td><button class="btn-del-row" onclick="deleteInitRow('${name}',${ri})">✕</button></td>
    </tr>`;
  }).join('') || `<tr><td colspan="${schema.length + 2}" class="no-rows">No rows yet — upload a file or add manually</td></tr>`;

  return `
    <div class="editor">
      <div class="ed-header">
        <div class="tag blue">initializer</div>
        <div>
          <h2>${name}
            <small>Edit rows to write to initializer/${name} on generate</small>
          </h2>
        </div>
      </div>

      ${agentBanner}

      <!-- Upload -->
      <div class="card">
        <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Load from file</h4></div>
        <div class="card-body">
          <div class="csv-zone">
            <input type="file" accept=".csv" onchange="loadInitCsvUpload('${name}',this)">
            Upload a CSV file to replace current rows
          </div>
        </div>
      </div>

      <!-- Rows table -->
      <div class="card">
        <div class="card-head">
          <div class="dot" style="background:#f0a500"></div>
          <h4>Rows — ${st.rows.length} entr${st.rows.length !== 1 ? 'ies' : 'y'}</h4>
        </div>
        <div class="table-toolbar">
          <button class="btn-sm accent" onclick="addInitRow('${name}')">+ Add Row</button>
          ${st.rows.length ? `<button class="btn-sm btn-clear" onclick="clearInitRows('${name}')">Clear All</button>` : ''}
        </div>
        <div class="card-body">
          <div class="tbl-wrap">
            <table class="data-table">
              <thead><tr><th class="col-idx">#</th>${colHeaders}<th class="col-del"></th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </div>
      </div>
    </div>`;
}

// ── Cell / row mutations ──────────────────────────────────────────────────────
function setInitCell(name, ri, col, val) {
  if (initializers[name]?.rows[ri]) {
    initializers[name].rows[ri][col] = val;
    if (name === 'network.csv') setTimeout(() => drawNetPreview(), 100);
  }
}

function addInitRow(name) {
  const st = initializers[name];
  if (!st) return;
  const row = {};
  st.schema.forEach(c => row[c] = '');
  st.rows.push(row);
  renderMain();
  renderInitNav();
}

function deleteInitRow(name, ri) {
  const st = initializers[name];
  if (!st) return;
  st.rows.splice(ri, 1);
  renderMain();
  renderInitNav();
  if (name === 'network.csv') setTimeout(() => { drawNetPreview(); initNetVirtScroll(); }, 80);
}

function clearInitRows(name) {
  const st = initializers[name];
  if (!st) return;
  st.rows = [];
  renderMain();
  renderInitNav();
  if (name === 'network.csv') setTimeout(() => { drawNetPreview(); initNetVirtScroll(); }, 80);
}

// ── CSV upload ────────────────────────────────────────────────────────────────
async function loadInitCsvUpload(name, input) {
  const file = input.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  fd.append('name', name);
  try {
    const r    = await fetch('/api/parse_initializer_csv', { method: 'POST', body: fd });
    const data = await r.json();
    if (data.error) { showToast(data.error); return; }
    initializers[name].rows = data.rows;
    renderMain();
    renderInitNav();
    if (name === 'network.csv') setTimeout(() => { drawNetPreview(); initNetVirtScroll(); }, 80);
  } catch (e) { showToast('Failed to parse CSV: ' + e.message); }
  input.value = '';
}
