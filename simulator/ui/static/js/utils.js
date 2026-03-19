// ── utils.js ──────────────────────────────────────────────────────────────────
// Tiny shared utilities used across all modules.

/** Escape a value for safe HTML attribute/text insertion. */
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Convert an arbitrary string into a CSS-safe id fragment. */
function cssId(s) {
  return s.replace(/[^a-zA-Z0-9]/g, '_');
}
