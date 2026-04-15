// utils.js — shared helpers

/** Query selector shorthand */
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

/** Build <option> tags; optionally prepend a blank/placeholder option */
function optTags(arr, selected = '', blankLabel = null) {
  const blank = blankLabel !== null
    ? `<option value=""${!selected ? ' selected' : ''}>${esc(blankLabel)}</option>`
    : '';
  return blank + arr.map(v =>
    `<option value="${esc(v)}"${v === selected ? ' selected' : ''}>${esc(v)}</option>`
  ).join('');
}

/** Format a ms timestamp as HH:MM:SS */
function fmtTime(ms) {
  const d = new Date(ms);
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
}

/** Format a ms timestamp as "Mon DD, HH:MM" */
function fmtDateTime(ms) {
  return new Date(ms).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}
