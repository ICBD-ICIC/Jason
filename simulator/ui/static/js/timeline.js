// timeline.js — dual-thumb histogram timeline
// Usage: const tl = new Timeline(messages, onRangeChange)
//   messages: array with .message.timestamp
//   onRangeChange: called when the range changes (after first drag)

const TL_BINS = 30;

class Timeline {
  constructor(msgs, onRangeChange) {
    this.msgs          = msgs;
    this.onRangeChange = onRangeChange;
    this.loFrac        = 0;
    this.hiFrac        = 1;
    this.active        = false;

    this.timestamps = msgs.map(m => m.message.timestamp).filter(Boolean).sort((a, b) => a - b);
    this.tMin = this.timestamps[0];
    this.tMax = this.timestamps[this.timestamps.length - 1];
    this.span = this.tMax - this.tMin || 1;

    this._init();
  }

  _init() {
    const el = document.getElementById('tl');
    if (!this.timestamps.length) { if (el) el.style.display = 'none'; return; }

    const { msgs, timestamps, tMin, tMax, span } = this;

    // Build bins
    this.bins = Array.from({ length: TL_BINS }, () => ({ total: 0, root: 0 }));
    for (const m of msgs) {
      const t = m.message.timestamp; if (!t) continue;
      const bi = Math.min(TL_BINS - 1, Math.floor((t - tMin) / span * TL_BINS));
      this.bins[bi].total++;
      if (+(m.variables?.public?.relation ?? 0) === 0) this.bins[bi].root++;
    }
    const maxBin = Math.max(...this.bins.map(b => b.total), 1);

    // Render histogram bars
    const histEl = document.getElementById('tl-hist');
    histEl.innerHTML = this.bins.map((b, i) => {
      const h = Math.max(3, Math.round((b.total / maxBin) * 44));
      return `<div class="tl-bar out" data-i="${i}" style="height:${h}px"></div>`;
    }).join('');
    this.barEls = histEl.querySelectorAll('.tl-bar');

    document.getElementById('tl-total').textContent = timestamps.length;

    // Wire thumb drag
    this.loEl    = document.getElementById('tl-lo');
    this.hiEl    = document.getElementById('tl-hi');
    this.rangeEl = document.getElementById('tl-range');
    this.lblLo   = document.getElementById('tl-lbl-lo');
    this.lblHi   = document.getElementById('tl-lbl-hi');
    this.cntEl   = document.getElementById('tl-count');

    this._bindThumb(this.loEl, 'lo');
    this._bindThumb(this.hiEl, 'hi');
    this._update();
  }

  _bindThumb(el, handle) {
    const onStart = (e) => {
      e.preventDefault();
      this.active = true;
      el.classList.add('dragging');

      const onMove = (ev) => {
        const rect = document.getElementById('tl-slider').getBoundingClientRect();
        const x    = (ev.touches?.[0] || ev).clientX;
        let f      = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
        if (handle === 'lo') this.loFrac = Math.min(f, this.hiFrac - 0.01);
        else                  this.hiFrac = Math.max(f, this.loFrac + 0.01);
        this._update();
      };
      const onUp = () => {
        el.classList.remove('dragging');
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup',   onUp);
        window.removeEventListener('touchmove', onMove);
        window.removeEventListener('touchend',  onUp);
      };
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup',   onUp);
      window.addEventListener('touchmove', onMove, { passive: false });
      window.addEventListener('touchend',  onUp);
    };

    el.addEventListener('mousedown',  onStart);
    el.addEventListener('touchstart', onStart, { passive: false });
  }

  _update() {
    const { tMin, span, loFrac, hiFrac, bins, barEls, cntEl, msgs } = this;
    const lo = tMin + loFrac * span;
    const hi = tMin + hiFrac * span;

    this.loEl.style.left    = (loFrac * 100) + '%';
    this.hiEl.style.left    = (hiFrac * 100) + '%';
    this.rangeEl.style.left  = (loFrac * 100) + '%';
    this.rangeEl.style.width = ((hiFrac - loFrac) * 100) + '%';
    this.lblLo.textContent   = fmtDateTime(lo);
    this.lblHi.textContent   = fmtDateTime(hi);

    barEls.forEach((el, i) => {
      const f       = (i + 0.5) / TL_BINS;
      const inRange = f >= loFrac && f <= hiFrac;
      const isRoot  = bins[i].root > 0 && bins[i].total === bins[i].root;
      el.className  = 'tl-bar ' + (inRange ? (isRoot ? 'root-in' : 'in') : (isRoot ? 'root-out' : 'out'));
    });

    cntEl.textContent = msgs.filter(m => {
      const t = m.message.timestamp;
      return !t || (t >= lo && t <= hi);
    }).length;

    if (this.active) this.onRangeChange();
  }

  /** Returns the currently visible subset of messages */
  visibleMsgs() {
    if (!this.active || !this.timestamps.length) return this.msgs;
    const lo = this.tMin + this.loFrac * this.span;
    const hi = this.tMin + this.hiFrac * this.span;
    return this.msgs.filter(m => {
      const t = m.message.timestamp;
      return !t || (t >= lo && t <= hi);
    });
  }
}
