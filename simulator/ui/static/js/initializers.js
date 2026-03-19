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
  const st = initializers[name];
  if (!st) return '';
  const schema = st.schema;

  const existingOpts = options.initializer_csvs.includes(name)
    ? `<option value="${name}">${name} (current)</option>`
    : options.initializer_csvs.map(f => `<option value="${f}">${f}</option>`).join('');

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
  }).join('') || `<tr><td colspan="${schema.length + 2}" class="no-rows">No rows yet — load a file or add manually</td></tr>`;

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

      <!-- Load from disk -->
      <div class="card">
        <div class="card-head"><div class="dot" style="background:var(--accent2)"></div><h4>Load from disk</h4></div>
        <div class="card-body">
          <div class="load-row">
            <label>Existing file:</label>
            <select id="init-file-sel-${cssId(name)}">${existingOpts || '<option value="">(none found)</option>'}</select>
            <button class="btn-sm accent" onclick="loadInitFromDisk('${name}')">Load</button>
          </div>
          <div class="csv-zone">
            <input type="file" accept=".csv" onchange="loadInitCsvUpload('${name}',this)">
            Or upload a CSV file to replace current rows
          </div>
        </div>
      </div>

      <!-- Rows table -->
      <div class="card">
        <div class="card-head">
          <div class="dot" style="background:#f0a500"></div>
          <h4>Rows — ${st.rows.length} entr${st.rows.length !== 1 ? 'ies' : 'y'}</h4>
        </div>
        <div class="card-body">
          <div class="tbl-wrap">
            <table class="data-table">
              <thead><tr><th class="col-idx">#</th>${colHeaders}<th class="col-del"></th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
          <div class="table-toolbar">
            <button class="btn-sm accent" onclick="addInitRow('${name}')">+ Add Row</button>
            ${st.rows.length ? `<button class="btn-sm" onclick="clearInitRows('${name}')">Clear All</button>` : ''}
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
  if (name === 'network.csv') setTimeout(() => drawNetPreview(), 80);
}

function clearInitRows(name) {
  const st = initializers[name];
  if (!st) return;
  st.rows = [];
  renderMain();
  renderInitNav();
  if (name === 'network.csv') setTimeout(() => drawNetPreview(), 80);
}

// ── Disk / upload loaders ────────────────────────────────────────────────────
async function loadInitFromDisk(name) {
  const sel   = document.getElementById('init-file-sel-' + cssId(name));
  const fname = sel?.value;
  if (!fname) return;
  try {
    const r    = await fetch('/api/load_initializer_csv?name=' + encodeURIComponent(fname));
    const data = await r.json();
    if (data.error) { showToast(data.error); return; }
    const st = initializers[name];
    st.rows = data.rows.map(row => {
      const out = {};
      st.schema.forEach(c => out[c] = (row[c] ?? ''));
      return out;
    });
    renderMain();
    renderInitNav();
    if (name === 'network.csv') setTimeout(() => drawNetPreview(), 80);
  } catch (e) { showToast('Failed to load: ' + e.message); }
}

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
    if (name === 'network.csv') setTimeout(() => drawNetPreview(), 80);
  } catch (e) { showToast('Failed to parse CSV: ' + e.message); }
  input.value = '';
}
