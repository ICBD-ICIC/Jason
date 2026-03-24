// ── modals.js ─────────────────────────────────────────────────────────────────
// Modal open/close, toast notifications, and the main Generate action.

// ── Modal helpers ─────────────────────────────────────────────────────────────
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// Close modals when clicking outside their content box
document.addEventListener('click', e => {
  ['out-modal', 'col-modal'].forEach(id => {
    const el = document.getElementById(id);
    if (e.target === el) closeModal(id);
  });
});

// ── Toast ─────────────────────────────────────────────────────────────────────
let _toastTimer;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('show'), 4200);
}

// ── Generate ──────────────────────────────────────────────────────────────────
async function generate() {
  const btn = document.getElementById('btn-gen');
  btn.disabled   = true;
  btn.textContent = 'Generating…';

  // Only send initializers that have rows
  const initPayload = {};
  for (const name of INIT_NAMES) {
    const st = initializers[name];
    if (st?.rows.length) initPayload[name] = st.rows;
  }

  const payload = {
    mas_name:       document.getElementById('mas-name').value.trim(),
    output_folder:  document.getElementById('output-folder').value.trim() || 'simulation_output',
    agent_types:  types.map(t => ({
      asl:        t.asl,
      arch_class: t.arch_class,
      bb_class:   t.bb_class,
      instances:  t.instances,
    })),
    initializers: initPayload,
  };

  try {
    const r    = await fetch('/api/generate', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { showToast((data.errors || ['Unknown error']).join(' | ')); return; }
    showOutputModal(data);
  } catch (e) {
    showToast('Request failed: ' + e.message);
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Generate Files';
  }
}

// ── Output modal ──────────────────────────────────────────────────────────────
function showOutputModal(data) {
  const files = (data.generated_files || [])
    .map(f => `<div class="file-chip">✓  ${f}</div>`)
    .join('');

  document.getElementById('out-modal-body').innerHTML = `
    <div class="ok-banner">✅&nbsp;
      <div>
        <strong>${data.generated_files?.length || 0} file(s) written</strong><br>
        <span style="color:var(--muted);font-size:.8rem">
          Output folder: <code>${esc(data.output_folder || '')}</code>
        </span><br>
        <span style="color:var(--muted);font-size:.8rem">
          Run: <code>./gradlew run -PmasFile=${esc(data.output_folder || '')}/${esc(data.mas_name || 'simulation_configured')}.mas2j</code>
        </span>
      </div>
    </div>
    <div>
      <div class="out-label">Generated Files</div>
      <div class="file-list">${files}</div>
    </div>
    <div>
      <div class="out-label">${esc(data.mas_name || 'simulation_configured')}.mas2j</div>
      <pre class="mas2j-out">${esc(data.mas2j || '')}</pre>
    </div>`;

  document.getElementById('out-modal').classList.add('open');
}
