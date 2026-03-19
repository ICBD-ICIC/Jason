// ── render.js ─────────────────────────────────────────────────────────────────
// Renders the sidebar (agent pills, initializer nav) and routes the main panel.

// ── Sidebar ───────────────────────────────────────────────────────────────────
function renderSidebar() {
  document.getElementById('agent-list').innerHTML = types.map(t => `
    <div class="agent-pill ${t.id === activeTypeId ? 'active' : ''}" onclick="selectType(${t.id})">
      <span class="pill-name">${t.asl || '(no file)'}</span>
      <span class="pill-count">${t.instances.length} inst</span>
      <button class="pill-del" onclick="deleteType(${t.id}, event)">✕</button>
    </div>`).join('');
}

function renderInitNav() {
  document.getElementById('init-nav').innerHTML = INIT_NAMES.map(name => {
    const st = initializers[name];
    return `<div class="init-pill ${name === activeInit ? 'active' : ''}" onclick="selectInit('${name}')">
      <span class="pill-name">${name}</span>
      <span class="pill-count">${st?.rows.length || 0} rows</span>
    </div>`;
  }).join('');
}

// ── Selection helpers ─────────────────────────────────────────────────────────
function selectType(id) {
  activeTypeId = id;
  activeInit   = null;
  renderSidebar();
  renderMain();
}

function selectInit(name) {
  activeInit   = name;
  activeTypeId = null;
  renderInitNav();
  renderMain();
}

// ── Main panel router ─────────────────────────────────────────────────────────
function renderMain() {
  const panel = document.getElementById('main-panel');

  if (activeTypeId !== null) {
    const t = types.find(t => t.id === activeTypeId);
    if (t) { panel.innerHTML = buildAgentEditor(t); return; }
  }

  if (activeInit) {
    panel.innerHTML = buildInitEditor(activeInit);
    // Network editor needs post-render setup (canvas draw)
    if (activeInit === 'network.csv') setTimeout(() => drawNetPreview(), 50);
    return;
  }

  panel.innerHTML = `
    <div class="empty-state">
      <div class="icon">⚙</div>
      <p>Add an agent type or select an initializer to begin</p>
    </div>`;
}
