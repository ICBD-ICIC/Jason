// render.js — sidebar + main panel routing

function renderSidebar() {
  setHtml('#agent-list', types.map(t => `
    <div class="agent-pill ${t.id === activeTypeId ? 'active' : ''}" onclick="selectType(${t.id})">
      <span class="pill-name">${esc(t.asl || '(no file)')}</span>
      <span class="pill-count">${t.instances.length} inst</span>
      <button class="pill-del" onclick="deleteType(${t.id},event)">✕</button>
    </div>`).join(''));
}

function renderInitNav() {
  setHtml('#init-nav', INIT_NAMES.map(name => {
    const st = initializers[name];
    return `<div class="init-pill ${name === activeInit ? 'active' : ''}" onclick="selectInit('${name}')">
      <span class="pill-name">${esc(name)}</span>
      <span class="pill-count">${st?.rows.length ?? 0} rows</span>
    </div>`;
  }).join(''));
}

function selectType(id) {
  activeTypeId = id; activeInit = null;
  renderSidebar(); renderMain();
}

function selectInit(name) {
  activeInit = name; activeTypeId = null;
  renderInitNav(); renderMain();
  if (name === 'network.csv') {
    setTimeout(() => { drawNetPreview(); _setupResizeHandle(); initNetVirtScroll(); }, 50);
  } else {
    // Boot virtual scroll for generic initializers (messages.csv, public_profiles.csv, …)
    setTimeout(() => initInitVirtScroll(name), 0);
  }
}

function renderMain() {
  const panel = $('#main-panel');

  if (activeTypeId !== null) {
    const t = types.find(t => t.id === activeTypeId);
    if (t) {
      panel.innerHTML = buildAgentEditor(t);
      setTimeout(() => initAgentVirtScroll(t.id), 0);
      return;
    }
  }

  if (activeInit) {
    panel.innerHTML = buildInitEditor(activeInit);
    if (activeInit === 'network.csv') {
      setTimeout(() => { drawNetPreview(); _setupResizeHandle(); initNetVirtScroll(); }, 50);
    } else {
      setTimeout(() => initInitVirtScroll(activeInit), 0);
    }
    return;
  }

  panel.innerHTML = `
    <div class="empty-state">
      <div class="icon">⚙</div>
      <p>Add an agent type or select an initializer to begin</p>
    </div>`;
}