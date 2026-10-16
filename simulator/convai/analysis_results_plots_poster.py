"""
analysis_results_plots_poster.py

Poster-ready plots for the CoNVaI / NeSy vs LLM-only simulation results.
Reads the same CSVs as analysis_results_plots.py.

What it produces (in --out_dir):
  fig_results_all.png / .svg      6-panel figure (Figure 1 of the paper), pooled over threads
  panels/panel_a_...png / .svg    the same 6 panels as separate files (for free layout in Canva)
  legend.png / .svg               standalone legend
  fig_messages_per_cycle.png/svg  messages per cycle, log scale (NeSy vs LLM-only)

Colours follow the poster template:
  green = symbolic / NeSy agent,  blue = LLM-only agent.
Change PALETTE below to match your exact Canva hex codes (eyedropper tool).

Usage:
  python analysis_results_plots_poster.py \
      --summary   convai/results.csv \
      --pv_pooled convai/results_pooled_delta.csv \
      --out_dir   convai/poster_plots

  # 3 rows x 2 columns instead of 2 x 3 (portrait block):
  python analysis_results_plots_poster.py ... --rows 3 --cols 2 --width 13 --height 16
"""
from __future__ import annotations

import argparse
import re
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Palette (poster template) ────────────────────────────────────────────────
PALETTE = {
    "blue":   "#5BC0EB",   # LLM call
    "green":  "#8CC63F",   # symbolic rule
    "orange": "#F5A623",   # input
    "yellow": "#FFE44D",
    "edge":   "#2B2B2B",
    "grid":   "#D9D9D9",
}
EDGE = PALETTE["edge"]

VARIANTS = ["600", "600_llm"]
COLOUR = {"600": PALETTE["green"], "600_llm": PALETTE["blue"]}
HATCH = {"600": "///", "600_llm": "..."}          # emptied by --no_hatch
VARIANT_LABEL = {"600": "NeSy (hybrid)", "600_llm": "LLM-only"}

CAUTIOUS_SUFFIXES = ["25pct_cautious", "50pct_cautious", "75pct_cautious"]
CREDULOUS_SUFFIXES = ["25pct_credulous", "50pct_credulous", "75pct_credulous"]
ALL_SUFFIXES = CAUTIOUS_SUFFIXES + CREDULOUS_SUFFIXES

CASE_LABELS_2LINE = {
    "baseline": "Baseline",
    "25pct_cautious": "Cautious\n25%", "50pct_cautious": "Cautious\n50%",
    "75pct_cautious": "Cautious\n75%",
    "25pct_credulous": "Credulous\n25%", "50pct_credulous": "Credulous\n50%",
    "75pct_credulous": "Credulous\n75%",
}

# Same order as Figure 1 of the paper: (letter, metric, panel title)
PANELS = [
    ("a", "vax_effectiveness_susc",       "Vaccination effectiveness"),
    ("b", "pct_infected_susc",            "Infected agents"),
    ("c", "pct_vaccinated_susc",          "Vaccinated agents"),
    ("d", "trans_neutral_to_infected",    "Neutral \u2192 infected"),
    ("e", "trans_neutral_to_vaccinated",  "Neutral \u2192 vaccinated"),
    ("f", "trans_infected_to_vaccinated", "Infected \u2192 vaccinated"),
]

STAR_THRESHOLDS = [(0.001, "***"), (0.01, "**"), (0.05, "*")]

# ── Font sizes (points, at the physical size of the figure) ──────────────────
FS: dict = {}


def apply_style(scale: float = 1.0, hatch: bool = True):
    FS.update(panel=25 * scale, sub=22 * scale, tick=21 * scale, label=22 * scale,
              star=24 * scale, legend=24 * scale, note=17 * scale)
    if not hatch:
        for k in HATCH:
            HATCH[k] = ""
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": EDGE,
        "axes.labelcolor": "#111111",
        "xtick.color": EDGE,
        "ytick.color": EDGE,
        "text.color": "#111111",
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
        "svg.fonttype": "path",          # text as outlines: SVGs look identical in Canva
        "hatch.linewidth": 1.4,
        "axes.unicode_minus": True,
    })


# ── Significance ─────────────────────────────────────────────────────────────
def stars(p) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    for thr, lbl in STAR_THRESHOLDS:
        if p < thr:
            return lbl
    return ""


def annotate_bar(ax, x, value, err, label, ylim):
    """Significance label at the outer end of the bar."""
    gap = (ylim[1] - ylim[0]) * 0.02
    if value >= 0:
        ax.text(x, value + err + gap, label, ha="center", va="bottom",
                fontsize=FS["star"], fontweight="bold", color=EDGE, zorder=6)
    else:
        ax.text(x, value - err - gap, label, ha="center", va="top",
                fontsize=FS["star"], fontweight="bold", color=EDGE, zorder=6)


# ── CSV loading ──────────────────────────────────────────────────────────────
def _read(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.exists():
        return None
    df = pd.read_csv(path)
    if "variant" in df.columns:
        df["variant"] = df["variant"].astype(str)
    return df


def load_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["variant"].astype(str).isin(VARIANTS)].copy()
    df["variant"] = df["variant"].astype(str)
    return df


def get_thread_ids(summary_df: pd.DataFrame) -> list[str]:
    tcs = summary_df["thread_config"].astype(str).unique()
    return sorted(tc for tc in tcs if re.fullmatch(r"\d+", tc))


def _f(v) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if np.isnan(v) else v


def get_mean_std(summary_df, variant, tc, metric):
    row = summary_df[(summary_df["variant"] == variant) &
                     (summary_df["thread_config"].astype(str) == tc)]
    if row.empty:
        return 0.0, 0.0
    r = row.iloc[0]
    return _f(r.get(f"{metric}_mean")), _f(r.get(f"{metric}_std", 0.0))


def get_run_vals(per_run_df, variant, tc, metric) -> list:
    if per_run_df is None or metric not in per_run_df.columns:
        return []
    sub = per_run_df[(per_run_df["variant"] == variant) &
                     (per_run_df["thread_config"].astype(str) == tc)]
    return sub[metric].dropna().tolist()


# ── P-value lookups (pooled preferred, per-thread legacy as fallback) ────────
def get_pv_pooled(df, variant, config, metric):
    if df is None:
        return None
    row = df[(df["variant"] == variant) & (df["config"] == config) & (df["metric"] == metric)]
    return None if row.empty else row.iloc[0]["p_wilcoxon"]


def get_pv_legacy(df, variant, thread_id, config, metric):
    if df is None or "thread_id" not in df.columns:
        return None
    row = df[(df["variant"] == variant) & (df["thread_id"].astype(str) == str(thread_id)) &
             (df["config"] == config) & (df["metric"] == metric)]
    return None if row.empty else row.iloc[0]["p_value"]


def resolve_pv(pv_pooled_df, pv_df, variant, thread_id, config, metric):
    p = get_pv_pooled(pv_pooled_df, variant, config, metric)
    return p if p is not None else get_pv_legacy(pv_df, variant, thread_id, config, metric)


# ── "All threads" aggregate rows ─────────────────────────────────────────────
def build_all_rows(summary_df: pd.DataFrame, thread_ids: list[str]) -> pd.DataFrame:
    metric_bases = [c[:-5] for c in summary_df.columns if c.endswith("_mean")]
    rows = []
    for variant in VARIANTS:
        sub = summary_df[summary_df["variant"] == variant].copy()
        sub["_suffix"] = sub["thread_config"].astype(str).apply(
            lambda tc: next(
                ("baseline" if tc == tid else tc[len(tid) + 1:]
                 for tid in thread_ids if tc == tid or tc.startswith(tid + "_")),
                None))
        sub = sub.dropna(subset=["_suffix"])
        for suffix, grp in sub.groupby("_suffix"):
            row = {"variant": variant,
                   "thread_config": "all" if suffix == "baseline" else f"all_{suffix}"}
            for m in metric_bases:
                vals = grp[f"{m}_mean"].dropna().values
                row[f"{m}_mean"] = float(np.mean(vals)) if len(vals) else None
                row[f"{m}_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            rows.append(row)
    return pd.DataFrame(rows)


# ── Saving ───────────────────────────────────────────────────────────────────
def save(fig, path_no_ext: Path, formats, dpi, transparent):
    path_no_ext.parent.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        fig.savefig(f"{path_no_ext}.{fmt}", format=fmt, dpi=dpi,
                    bbox_inches="tight", pad_inches=0.05, transparent=transparent)
    plt.close(fig)
    print(f"  saved {path_no_ext}.[{', '.join(formats)}]")


def legend_handles():
    return [mpatches.Patch(facecolor=COLOUR[v], hatch=HATCH[v], edgecolor=EDGE,
                           linewidth=1.2, label=VARIANT_LABEL[v]) for v in VARIANTS]


def note_text() -> str:
    thr = "   ".join(f"{lbl} p < {t}" for t, lbl in reversed(STAR_THRESHOLDS))
    return ("\u0394% relative to baseline. x-axis: share of cautious / credulous agents "
            "in the population.\n" + thr + " (pooled Wilcoxon signed-rank vs baseline)")


# ── Panel: cautious | credulous, delta vs baseline ───────────────────────────
def delta_data(summary_df, tid, metric, suffixes):
    out = {}
    for variant in VARIANTS:
        bl_m, bl_s = get_mean_std(summary_df, variant, tid, metric)
        ys, es = [], []
        for suf in suffixes:
            m, s = get_mean_std(summary_df, variant, f"{tid}_{suf}", metric)
            ys.append(m - bl_m)
            es.append(float(np.hypot(s, bl_s)))       # error in quadrature
        out[variant] = (np.array(ys), np.array(es))
    return out


def draw_panel(fig, spec, letter, metric, title, tid,
               summary_df, pv_df, pv_pooled_df, per_run_df, show_runs):
    groups = [("Cautious", CAUTIOUS_SUFFIXES), ("Credulous", CREDULOUS_SUFFIXES)]
    data = [delta_data(summary_df, tid, metric, sufs) for _, sufs in groups]

    # common y-limits for both sub-axes, with room for the stars
    lo = hi = 0.0
    for d in data:
        for v in VARIANTS:
            ys, es = d[v]
            lo, hi = min(lo, float((ys - es).min())), max(hi, float((ys + es).max()))
    pad = 0.18 * max(hi - lo, 1e-6)
    ylim = (lo - pad, hi + pad)

    # invisible axes spanning the whole panel: carries the panel title
    tax = fig.add_subplot(spec, frameon=False)
    tax.set_xticks([])
    tax.set_yticks([])
    tax.set_title(f"({letter}) {title}", fontsize=FS["panel"], fontweight="bold",
                  pad=FS["sub"] * 1.7 + 6)

    inner = spec.subgridspec(1, 2, wspace=0.10)
    x = np.arange(3)
    w = 0.38
    first = None
    for i, ((gname, sufs), d) in enumerate(zip(groups, data)):
        ax = fig.add_subplot(inner[0, i], sharey=first)
        first = first or ax
        for vi, v in enumerate(VARIANTS):
            ys, es = d[v]
            off = (vi - 0.5) * w
            ax.bar(x + off, ys, w, color=COLOUR[v], hatch=HATCH[v], edgecolor=EDGE,
                   linewidth=1.2, yerr=es, capsize=4, zorder=3,
                   error_kw={"elinewidth": 1.4, "ecolor": EDGE, "capthick": 1.4})
            if show_runs and per_run_df is not None:
                bl = get_run_vals(per_run_df, v, tid, metric)
                bl_mean = float(np.mean(bl)) if bl else 0.0
                for ci, suf in enumerate(sufs):
                    vals = get_run_vals(per_run_df, v, f"{tid}_{suf}", metric)
                    if vals:
                        jx = np.random.normal(x[ci] + off, 0.04, size=len(vals))
                        ax.scatter(jx, [q - bl_mean for q in vals], color="black",
                                   s=22, zorder=5, alpha=0.7, linewidths=0)
            for ci, suf in enumerate(sufs):
                s = stars(resolve_pv(pv_pooled_df, pv_df, v, tid, suf, metric))
                if s:
                    annotate_bar(ax, x[ci] + off, ys[ci], es[ci], s, ylim)

        ax.set_ylim(*ylim)
        ax.axhline(0, color=EDGE, lw=1.6, ls="--", zorder=2)
        ax.set_xticks(x)
        ax.set_xticklabels(["25%", "50%", "75%"], fontsize=FS["tick"])
        ax.tick_params(axis="y", labelsize=FS["tick"], width=1.4, length=6)
        ax.tick_params(axis="x", width=1.4, length=6)
        ax.set_title(gname, fontsize=FS["sub"], pad=8)
        ax.yaxis.grid(True, color=PALETTE["grid"], lw=0.9)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_linewidth(1.4)
        if i == 0:
            ax.set_ylabel("\u0394%", fontsize=FS["label"])
        else:
            ax.tick_params(labelleft=False, left=False)
            ax.spines["left"].set_visible(False)


# ── Combined 6-panel figure ──────────────────────────────────────────────────
def make_combined(tid, name, summary_df, pv_df, pv_pooled_df, per_run_df, show_runs,
                  out_dir, rows, cols, W, H, formats, dpi, transparent):
    fig = plt.figure(figsize=(W, H))

    # Margins in inches so they stay right for any figure size
    left_in, right_in, top_in, bottom_in = 1.2, 0.2, 1.15, 2.0
    gap_h_in = (FS["sub"] * 1.7 + 6 + FS["panel"] * 1.3 + FS["tick"] * 2.2) / 72 + 0.15
    gap_w_in = 1.1
    avail_h = H - top_in - bottom_in
    avail_w = W - left_in - right_in
    ax_h = (avail_h - (rows - 1) * gap_h_in) / rows
    ax_w = (avail_w - (cols - 1) * gap_w_in) / cols
    outer = fig.add_gridspec(rows, cols,
                             left=left_in / W, right=1 - right_in / W,
                             top=1 - top_in / H, bottom=bottom_in / H,
                             hspace=gap_h_in / ax_h, wspace=gap_w_in / ax_w)

    for idx, (letter, metric, title) in enumerate(PANELS[: rows * cols]):
        r, c = divmod(idx, cols)
        draw_panel(fig, outer[r, c], letter, metric, title, tid,
                   summary_df, pv_df, pv_pooled_df, per_run_df, show_runs)

    fig.legend(handles=legend_handles(), loc="lower center",
               bbox_to_anchor=(0.5, 0.85 / H), ncol=2, frameon=False,
               fontsize=FS["legend"], handlelength=2.2, handleheight=1.3,
               columnspacing=2.5)
    fig.text(0.5, 0.08 / H, note_text(), ha="center", va="bottom",
             fontsize=FS["note"], color="#444444", linespacing=1.4)
    save(fig, out_dir / name, formats, dpi, transparent)


# ── Individual panels ────────────────────────────────────────────────────────
def make_single_panels(tid, summary_df, pv_df, pv_pooled_df, per_run_df, show_runs,
                       out_dir, formats, dpi, transparent):
    slug = {"a": "vax_effectiveness", "b": "infected", "c": "vaccinated",
            "d": "neutral_to_infected", "e": "neutral_to_vaccinated",
            "f": "infected_to_vaccinated"}
    W, H = 7.6, 5.4
    for letter, metric, title in PANELS:
        fig = plt.figure(figsize=(W, H))
        gs = fig.add_gridspec(1, 1, left=1.2 / W, right=1 - 0.2 / W,
                              top=1 - 1.15 / H, bottom=0.7 / H)
        draw_panel(fig, gs[0, 0], letter, metric, title, tid,
                   summary_df, pv_df, pv_pooled_df, per_run_df, show_runs)
        save(fig, out_dir / "panels" / f"panel_{letter}_{slug[letter]}",
             formats, dpi, transparent)


def make_legend_file(out_dir, formats, dpi, transparent):
    fig = plt.figure(figsize=(6, 0.9))
    fig.legend(handles=legend_handles(), loc="center", ncol=2, frameon=False,
               fontsize=FS["legend"], handlelength=2.2, handleheight=1.3, columnspacing=2.5)
    save(fig, out_dir / "legend", formats, dpi, transparent)


# ── Messages per cycle (log scale) ───────────────────────────────────────────
def make_messages_plot(tid, summary_df, out_dir, formats, dpi, transparent, W=13, H=6.5):
    metric = "messages_per_cycle"
    if f"{metric}_mean" not in summary_df.columns:
        print("  (skipping messages plot: messages_per_cycle not in summary CSV)")
        return
    configs = ["baseline"] + ALL_SUFFIXES
    fig, ax = plt.subplots(figsize=(W, H))
    x = np.arange(len(configs))
    w = 0.38
    for vi, v in enumerate(VARIANTS):
        ys, es = [], []
        for cfg in configs:
            tc = tid if cfg == "baseline" else f"{tid}_{cfg}"
            m, s = get_mean_std(summary_df, v, tc, metric)
            ys.append(m)
            es.append(s)
        ys, es = np.array(ys), np.array(es)
        lower = np.minimum(es, ys * 0.9)              # keeps error bars valid on a log axis
        ax.bar(x + (vi - 0.5) * w, np.where(ys > 0, ys, np.nan), w,
               color=COLOUR[v], hatch=HATCH[v], edgecolor=EDGE, linewidth=1.2,
               yerr=[lower, es], capsize=4, zorder=3,
               error_kw={"elinewidth": 1.4, "ecolor": EDGE, "capthick": 1.4})
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([CASE_LABELS_2LINE[c] for c in configs], fontsize=FS["tick"])
    ax.tick_params(axis="y", labelsize=FS["tick"], width=1.4, length=6)
    ax.set_ylabel("Messages per cycle (log scale)", fontsize=FS["label"])
    ax.yaxis.grid(True, color=PALETTE["grid"], lw=0.9)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_linewidth(1.4)
    ax.legend(handles=legend_handles(), loc="upper center", bbox_to_anchor=(0.5, -0.2),
              ncol=2, frameon=False, fontsize=FS["legend"], handlelength=2.2,
              handleheight=1.3, columnspacing=2.5)
    save(fig, out_dir / "fig_messages_per_cycle", formats, dpi, transparent)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    np.random.seed(42)
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="convai/results.csv")
    ap.add_argument("--pv_bl", default="convai/results_pvalues_variant_vs_baseline.csv",
                    help="Legacy per-thread p-values (fallback only; optional).")
    ap.add_argument("--pv_pooled", default="convai/results_pooled_delta.csv",
                    help="Pooled p-values (variant, config, metric, p_wilcoxon).")
    ap.add_argument("--per_run", default="convai/results_per_run.csv")
    ap.add_argument("--out_dir", default="convai/poster_plots")
    ap.add_argument("--rows", type=int, default=2, help="Panel grid rows (rows*cols must be 6).")
    ap.add_argument("--cols", type=int, default=3, help="Panel grid columns.")
    ap.add_argument("--width", type=float, default=20.0, help="Combined figure width (inches).")
    ap.add_argument("--height", type=float, default=10.5, help="Combined figure height (inches).")
    ap.add_argument("--font_scale", type=float, default=1.0)
    ap.add_argument("--formats", nargs="+", default=["png", "svg"])
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--transparent", action="store_true", help="Transparent background.")
    ap.add_argument("--no_hatch", action="store_true", help="Flat colours, no hatching.")
    ap.add_argument("--show_runs", action="store_true",
                    help="Overlay individual run points (per-thread only).")
    ap.add_argument("--per_thread", action="store_true",
                    help="Also make the combined figure for each thread.")
    args = ap.parse_args()

    apply_style(args.font_scale, hatch=not args.no_hatch)

    summary_df = load_summary(Path(args.summary))
    pv_df = _read(Path(args.pv_bl))
    pv_pooled_df = _read(Path(args.pv_pooled))
    per_run_df = _read(Path(args.per_run))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if pv_pooled_df is None:
        print(f"WARNING: pooled p-values not found at '{args.pv_pooled}'; "
              "stars will come from the per-thread file (if any).")

    thread_ids = get_thread_ids(summary_df)
    print(f"Threads found: {thread_ids}")
    combined_df = pd.concat([summary_df, build_all_rows(summary_df, thread_ids)],
                            ignore_index=True)

    fmts = args.formats
    print("\n-- Combined figure (all threads) --")
    make_combined("all", "fig_results_all", combined_df, pv_df, pv_pooled_df, per_run_df,
                  args.show_runs, out_dir, args.rows, args.cols, args.width, args.height,
                  fmts, args.dpi, args.transparent)
    if args.per_thread:
        for tid in thread_ids:
            make_combined(tid, f"fig_results_{tid}", combined_df, pv_df, pv_pooled_df,
                          per_run_df, args.show_runs, out_dir, args.rows, args.cols,
                          args.width, args.height, fmts, args.dpi, args.transparent)

    print("\n-- Individual panels --")
    make_single_panels("all", combined_df, pv_df, pv_pooled_df, per_run_df, args.show_runs,
                       out_dir, fmts, args.dpi, args.transparent)

    print("\n-- Legend --")
    make_legend_file(out_dir, fmts, args.dpi, args.transparent)

    print("\n-- Messages per cycle --")
    make_messages_plot("all", combined_df, out_dir, fmts, args.dpi, args.transparent)

    print(f"\nDone. Files in '{out_dir}/'")


if __name__ == "__main__":
    main()