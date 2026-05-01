// modals.js — modal helpers, toast, generate action

function closeModal(id) { $(`#${id}`).classList.remove('open'); }

document.addEventListener('click', e => {
  ['out-modal', 'col-modal'].forEach(id => {
    if (e.target === $(`#${id}`)) closeModal(id);
  });
});

// ── Toast ──────────────────────────────────────────────────────────────────────
let _toastTimer;
function showToast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('show'), 4200);
}

// ── Generate ───────────────────────────────────────────────────────────────────
async function generate() {
  const btn = $('#btn-gen');
  btn.disabled = true; btn.textContent = 'Generating…';

  const initPayload = Object.fromEntries(
    INIT_NAMES.filter(n => initializers[n]?.rows.length).map(n => [n, initializers[n].rows])
  );

  const payload = {
    mas_name:       $('#mas-name').value.trim(),
    output_folder:  $('#output-folder').value.trim(),
    mind_inspector: $('#mind-inspector').checked,
    silent_logging: $('#silent-logging').checked,
    agent_types:    types.map(({ asl, arch_class, bb_class, instances }) => ({ asl, arch_class, bb_class, instances })),
    initializers:   initPayload,
  };

  try {
    const r    = await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await r.json();
    if (!data.ok) { showToast((data.errors || ['Unknown error']).join(' | ')); return; }
    showOutputModal(data);
  } catch (e) {
    showToast('Request failed: ' + e.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Generate Files';
  }
}

// ── Output modal ───────────────────────────────────────────────────────────────
function showOutputModal(data) {
  const files = (data.generated_files || []).map(f => `<div class="file-chip">✓ ${esc(f)}</div>`).join('');
  let cmd = 'gradle clean run';
  if (data.output_folder) cmd += ` -PgeneratedFolder=${esc(data.output_folder)}`;
  if (data.mas_name)      cmd += ` -PmasFile=${esc(data.mas_name)}.mas2j`;

  setHtml('#out-modal-body', `
    <div class="ok-banner">
      <div>
        <strong>${(data.generated_files?.length || 0)} file(s) written</strong><br>
        <span style="color:var(--muted);font-size:.8rem">Folder: <code>${esc(data.output_folder || '')}</code></span><br>
        <span style="color:var(--muted);font-size:.8rem">Run: <code>${cmd}</code></span>
      </div>
    </div>
    <div><div class="out-label">Generated Files</div><div class="file-list">${files}</div></div>
    <div>
      <div class="out-label">${esc(data.mas_name || 'simulation_configured')}.mas2j</div>
      <pre class="mas2j-out">${esc(data.mas2j || '')}</pre>
    </div>`);

  $('#out-modal').classList.add('open');
}
