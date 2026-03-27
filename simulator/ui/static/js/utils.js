// utils.js — shared helpers

const $ = (sel, ctx = document) => ctx.querySelector(sel);

/** HTML-escape a value */
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Set innerHTML by selector or element */
function setHtml(target, markup) {
  const el = typeof target === 'string' ? $(target) : target;
  if (el) el.innerHTML = markup;
}

/** Build <option> tags; optionally prepend a blank option */
function optTags(arr, selected = '', blankLabel = null) {
  const blank = blankLabel !== null
    ? `<option value=""${!selected ? ' selected' : ''}>${esc(blankLabel)}</option>`
    : '';
  return blank + arr.map(v =>
    `<option value="${esc(v)}"${v === selected ? ' selected' : ''}>${esc(v)}</option>`
  ).join('');
}
