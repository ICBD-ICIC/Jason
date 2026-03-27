// initializers.js — generic initializer editor (messages.csv, public_profiles.csv)

function buildInitEditor(name) {
  if (name === 'network.csv') return buildNetworkEditor(name);
  return buildGenericInitEditor(name);
}

function buildGenericInitEditor(name) {
  const st = initializers[name]; if (!st) return '';
  const { schema, rows } = st;
  const agents   = getAllAgentNames();
  const isProfiles = name === 'public_profiles.csv';

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

  const headers = schema.map(c => `<th>${esc(c)}</th>`).join('');
  const bodyRows = rows.map((row, ri) => `
    <tr>
      <td class="td-idx">${ri + 1}</td>
      ${schema.map(c => `<td><input type="text" value="${esc(row[c] ?? '')}"
        oninput="setInitCell('${name}',${ri},'${c}',this.value)"></td>`).join('')}
      <td><button class="btn-del-row" onclick="deleteInitRow('${name}',${ri})">✕</button></td>
    </tr>`).join('') || `<tr><td colspan="${schema.length + 2}" class="no-rows">No rows yet — upload a file or add manually</td></tr>`;

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
          <h4>Rows — ${rows.length} entr${rows.length !== 1 ? 'ies' : 'y'}</h4>
        </div>
        <div class="table-toolbar">
          <button class="btn-sm accent" onclick="addInitRow('${name}')">+ Add Row</button>
          ${rows.length ? `<button class="btn-sm btn-clear" onclick="clearInitRows('${name}')">Clear All</button>` : ''}
        </div>
        <div class="card-body">
          <div class="tbl-wrap"><table class="data-table">
            <thead><tr><th class="col-idx">#</th>${headers}<th class="col-del"></th></tr></thead>
            <tbody>${bodyRows}</tbody>
          </table></div>
        </div>
      </div>
    </div>`;
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
  renderMain(); renderInitNav();
}

function deleteInitRow(name, ri) {
  initializers[name]?.rows.splice(ri, 1);
  renderMain(); renderInitNav();
  if (name === 'network.csv') setTimeout(() => { drawNetPreview(); initNetVirtScroll(); }, 80);
}

function clearInitRows(name) {
  if (initializers[name]) initializers[name].rows = [];
  renderMain(); renderInitNav();
  if (name === 'network.csv') setTimeout(() => { drawNetPreview(); initNetVirtScroll(); }, 80);
}

async function loadInitCsvUpload(name, input) {
  const file = input.files[0]; if (!file) return;
  const fd = new FormData(); fd.append('file', file); fd.append('name', name);
  try {
    const data = await fetch('/api/parse_initializer_csv', { method: 'POST', body: fd }).then(r => r.json());
    if (data.error) { showToast(data.error); return; }
    initializers[name].rows = data.rows;
    renderMain(); renderInitNav();
    if (name === 'network.csv') setTimeout(() => { drawNetPreview(); initNetVirtScroll(); }, 80);
  } catch (e) { showToast('Failed to parse CSV: ' + e.message); }
  input.value = '';
}
