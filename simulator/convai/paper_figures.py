"""
paper_figures.py

Replots the 6 delta figures used in the paper, optimised for small
multi-panel layouts:
  - No subplot titles
  - Squashed, narrow bars with tight spacing
  - Large fonts (all ≥ 20 pt)
  - Individual run jitter points (optional)
  - Significance stars from pooled p-values

Produces 6 individual PDFs (one per panel a–f) + a separate legend PDF.

Usage:
    python paper_figures.py \\
        --summary   convai/results.csv \\
        --pv_pooled convai/results_pvalues_pooled.csv \\
        --per_run   convai/results_per_run.csv \\
        --out_dir   convai/paper_figs/

    # Legacy fallback (no longer drives stars):
        --pv_bl     convai/results_pvalues_variant_vs_baseline.csv
"""

import argparse
import re
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Colours & styles
# ---------------------------------------------------------------------------
COLOUR  = {"600": "#FF2D8B", "600_llm": "#00E676"}
HATCH   = {"600": "///",     "600_llm": "..."}
VARIANT_LABEL = {"600": "600", "600_llm": "600-LLM"}

CAUTIOUS_SUFFIXES  = ["25pct_cautious",  "50pct_cautious",  "75pct_cautious"]
CREDULOUS_SUFFIXES = ["25pct_credulous", "50pct_credulous", "75pct_credulous"]

CASE_LABELS = {
    "25pct_cautious":   "25%",
    "50pct_cautious":   "50%",
    "75pct_cautious":   "75%",
    "25pct_credulous":  "25%",
    "50pct_credulous":  "50%",
    "75pct_credulous":  "75%",
}

STAR_THRESHOLDS = [(0.001, "***"), (0.01, "**"), (0.05, "*")]

# ---------------------------------------------------------------------------
# Font sizes — everything large so it reads at paper column width
# ---------------------------------------------------------------------------
FS_AXLABEL = 22   # y-axis label
FS_TICK    = 20   # tick labels
FS_ANNOT   = 20   # significance stars
FS_LEGEND  = 22   # legend text

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   "white",
    "axes.edgecolor":   "#333333",
    "axes.labelcolor":  "#111111",
    "xtick.color":      "#333333",
    "ytick.color":      "#333333",
    "text.color":       "#111111",
    "grid.color":       "#dddddd",
    "grid.linewidth":   0.6,
    "font.size":        FS_TICK,
    "axes.titlesize":   FS_AXLABEL,
    "axes.labelsize":   FS_AXLABEL,
    "xtick.labelsize":  FS_TICK,
    "ytick.labelsize":  FS_TICK,
    "legend.fontsize":  FS_LEGEND,
})

# ---------------------------------------------------------------------------
# The 6 panels (a)–(f) as ordered in the paper
# ---------------------------------------------------------------------------
PANELS = [
    # (filename_stem,  metric,                      ylabel,                           cautious_or_credulous)
    ("all_vax_effectiveness_delta",  "vax_effectiveness_susc",    r"$\Delta$% Vax. Effectiveness",   "both"),
    ("all_pct_infected_susc_delta",       "pct_infected_susc",         r"$\Delta$% Infected agents",       "both"),
    ("all_pct_vaccinated_susc_delta",     "pct_vaccinated_susc",       r"$\Delta$% Vaccinated agents",     "both"),
    ("all_trans_neutral_to_infected",   "trans_neutral_to_infected", r"$\Delta$% Neutral$\to$Infected",  "both"),
    ("all_trans_neutral_to_vaccinated", "trans_neutral_to_vaccinated",r"$\Delta$% Neutral$\to$Vaccinated","both"),
    ("all_trans_infected_to_vaccinated","trans_infected_to_vaccinated",r"$\Delta$% Infected$\to$Vaccinated","both"),
]

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_summary(path):
    df = pd.read_csv(path)
    df = df[df["variant"].isin(["600", "600_llm"])].copy()
    df["variant"] = df["variant"].astype(str)
    return df

def load_pv_baseline(path):
    df = pd.read_csv(path)
    df["variant"] = df["variant"].astype(str)
    return df

def load_pv_pooled(path):
    if path is None or not Path(path).exists():
        return None
    df = pd.read_csv(path)
    df["variant"] = df["variant"].astype(str)
    return df

def load_per_run(path):
    if path is None or not Path(path).exists():
        return None
    df = pd.read_csv(path)
    df["variant"] = df["variant"].astype(str)
    return df

def get_thread_ids(summary_df):
    tcs = summary_df["thread_config"].astype(str).unique()
    return sorted(tc for tc in tcs if re.fullmatch(r"\d+", tc))

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def get_mean_std(summary_df, variant, tc, metric):
    row = summary_df[(summary_df["variant"] == variant) &
                     (summary_df["thread_config"].astype(str) == tc)]
    if row.empty:
        return None, 0.0
    return row.iloc[0].get(f"{metric}_mean"), row.iloc[0].get(f"{metric}_std", 0.0)

def get_pv(pv_df, variant, thread_id, config, metric):
    row = pv_df[
        (pv_df["variant"]   == variant) &
        (pv_df["thread_id"].astype(str) == str(thread_id)) &
        (pv_df["config"]    == config) &
        (pv_df["metric"]    == metric)
    ]
    if row.empty:
        return None
    return row.iloc[0]["p_value"]

def get_pv_pooled(pv_pooled_df, variant, config, metric):
    if pv_pooled_df is None:
        return None
    row = pv_pooled_df[
        (pv_pooled_df["variant"] == variant) &
        (pv_pooled_df["config"]  == config) &
        (pv_pooled_df["metric"]  == metric)
    ]
    if row.empty:
        return None
    return row.iloc[0]["p_wilcoxon"]

def resolve_pv(pv_pooled_df, pv_df, variant, thread_id, config, metric):
    p = get_pv_pooled(pv_pooled_df, variant, config, metric)
    if p is not None:
        return p
    return get_pv(pv_df, variant, thread_id, config, metric)

def get_run_vals(per_run_df, variant, tc, metric):
    if per_run_df is None:
        return []
    sub = per_run_df[(per_run_df["variant"] == variant) &
                     (per_run_df["thread_config"].astype(str) == tc)]
    return sub[metric].dropna().tolist()

def stars(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    for thr, lbl in STAR_THRESHOLDS:
        if p < thr:
            return lbl
    return ""

def build_all_rows(summary_df, thread_ids):
    metric_bases = [c[:-5] for c in summary_df.columns if c.endswith("_mean")]
    rows = []
    for variant in ["600", "600_llm"]:
        sub = summary_df[summary_df["variant"] == variant].copy()
        sub["_suffix"] = sub["thread_config"].astype(str).apply(
            lambda tc: next(
                ("baseline" if tc == tid else tc[len(tid) + 1:]
                 for tid in thread_ids if tc == tid or tc.startswith(tid + "_")),
                None
            )
        )
        sub = sub.dropna(subset=["_suffix"])
        for suffix, grp in sub.groupby("_suffix"):
            tc_label = "all" if suffix == "baseline" else f"all_{suffix}"
            row = {"variant": variant, "thread_config": tc_label}
            for m in metric_bases:
                vals = grp[f"{m}_mean"].dropna().values
                row[f"{m}_mean"] = float(np.mean(vals)) if len(vals) else None
                row[f"{m}_std"]  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            rows.append(row)
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# Core delta-bar renderer (no title, squashed bars)
# ---------------------------------------------------------------------------

def annotate_bar(ax, x, bar_value, error, label):
    if not label:
        return
    ylim = ax.get_ylim()
    axis_span = max(abs(ylim[1] - ylim[0]), 1e-6)
    gap = axis_span * 0.008

    if bar_value >= 0:
        y, va = bar_value + gap, "bottom"
    else:
        y, va = bar_value - gap, "top"

    ax.text(x, y, label, ha="center", va=va, fontsize=FS_ANNOT,
            fontweight="bold", color="#222222")


def plot_panel(ax, suffixes, summary_df, thread_id, metric,
               pv_df, pv_pooled_df, ylabel, per_run_df=None,
               show_ylabel=True, group_label=None):
    """
    Draws Δ-vs-baseline bars for one Cautious or Credulous half-panel.
    No title. Narrow bars. Large fonts.
    """
    # Narrower bars + tighter x-spacing to squash everything
    bar_w = 0.30
    x     = np.arange(len(suffixes)) * 0.85   # compress x-axis

    for vi, variant in enumerate(["600", "600_llm"]):
        offset = (vi - 0.5) * bar_w
        tc_bl  = thread_id
        bl_m, bl_s = get_mean_std(summary_df, variant, tc_bl, metric)
        bl_m = bl_m or 0.0

        ys, es = [], []
        for suf in suffixes:
            tc = f"{thread_id}_{suf}"
            m, s = get_mean_std(summary_df, variant, tc, metric)
            ys.append((m or 0.0) - bl_m)
            es.append(np.sqrt((s or 0.0) ** 2 + (bl_s or 0.0) ** 2))

        ax.bar(x + offset, ys, bar_w,
               color=COLOUR[variant], hatch=HATCH[variant],
               edgecolor="#333333", linewidth=0.7,
               alpha=0.85, label=VARIANT_LABEL[variant],
               yerr=es, capsize=3,
               error_kw={"elinewidth": 0.9, "ecolor": "#555555"})

        # Jitter individual run deltas
        if per_run_df is not None:
            bl_vals = get_run_vals(per_run_df, variant, tc_bl, metric)
            bl_mean_run = float(np.mean(bl_vals)) if bl_vals else bl_m
            for ci, suf in enumerate(suffixes):
                tc = f"{thread_id}_{suf}"
                vals = get_run_vals(per_run_df, variant, tc, metric)
                if vals:
                    deltas = [v - bl_mean_run for v in vals]
                    jx = np.random.normal(x[ci] + offset, 0.03, size=len(deltas))
                    ax.scatter(jx, deltas, color="black", s=12, zorder=5,
                               alpha=0.65, linewidths=0)

        # Stars
        for ci, suf in enumerate(suffixes):
            p = resolve_pv(pv_pooled_df, pv_df, variant, thread_id, suf, metric)
            s = stars(p)
            if s:
                annotate_bar(ax, x[ci] + offset, ys[ci], es[ci], s)

    ax.axhline(0, color="#333333", linewidth=0.9, linestyle="--", alpha=0.7)

    # X-ticks
    short_labels = [CASE_LABELS.get(s, s) for s in suffixes]
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, fontsize=FS_TICK)

    if show_ylabel:
        ax.set_ylabel(ylabel, fontsize=16)
    else:
        ax.set_ylabel("")
        ax.tick_params(labelleft=False)

    # Optional group label (Cautious / Credulous) as a text annotation instead of title
    if group_label:
        ax.text(0.5, 1.01, group_label, transform=ax.transAxes,
                ha="center", va="bottom", fontsize=FS_TICK + 1,
                fontweight="bold", color="#333333")

    ax.yaxis.grid(True, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", labelsize=FS_TICK)

    # Limit x-axis padding
    ax.set_xlim(x[0] - bar_w * 1.8, x[-1] + bar_w * 1.8)

# ---------------------------------------------------------------------------
# Save individual panel PDF
# ---------------------------------------------------------------------------

def save_panel(stem, metric, ylabel, summary_df, pv_df, pv_pooled_df,
               per_run_df, out_dir):
    """
    One figure with two sub-axes side by side: Cautious | Credulous.
    No suptitle. Tight layout.
    """
    thread_id = "all"   # aggregate across all threads (matches paper)

    # Figure sized to fit ~2-column panel in a paper: wide & short
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.8),
                             gridspec_kw={"wspace": 0.08})

    for i, (ax, (group_name, suffixes)) in enumerate(zip(
        axes,
        [("Cautious", CAUTIOUS_SUFFIXES), ("Credulous", CREDULOUS_SUFFIXES)]
    )):
        plot_panel(
            ax, suffixes, summary_df, thread_id, metric,
            pv_df, pv_pooled_df, ylabel,
            per_run_df=per_run_df,
            show_ylabel=(i == 0),
            group_label=group_name,
        )

    fig.tight_layout(pad=0.2, rect=[0, 0, 1, 0.96])

    fname = out_dir / f"{stem}.pdf"
    fig.savefig(fname, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {fname.name}")

# ---------------------------------------------------------------------------
# Separate legend PDF
# ---------------------------------------------------------------------------

def save_legend(out_dir):
    """
    Horizontal legend with the two variant patches only.
    Saves as a thin strip PDF.
    """
    fig, ax = plt.subplots(figsize=(4.5, 0.65))
    ax.set_visible(False)

    handles = [
        mpatches.Patch(facecolor=COLOUR[v], hatch=HATCH[v],
                       edgecolor="#333333", alpha=0.85,
                       label=VARIANT_LABEL[v])
        for v in ["600", "600_llm"]
    ]
    leg = fig.legend(
        handles=handles,
        loc="center",
        ncol=2,
        fontsize=FS_LEGEND,
        framealpha=0.0,
        edgecolor="none",
        handlelength=2.5,
        handleheight=1.6,
        columnspacing=2.0,
    )

    fname = out_dir / "legend.pdf"
    fig.savefig(fname, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {fname.name}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    np.random.seed(42)

    parser = argparse.ArgumentParser()
    parser.add_argument("--summary",   default="convai/results.csv")
    parser.add_argument("--pv_bl",     default="convai/results_pvalues_variant_vs_baseline.csv")
    parser.add_argument("--pv_pooled", default="convai/results_pooled_delta.csv")
    parser.add_argument("--per_run",   default="convai/results_per_run.csv")
    parser.add_argument("--out_dir",   default="convai/paper_figs")
    args = parser.parse_args()

    summary_df   = load_summary(Path(args.summary))
    pv_df        = load_pv_baseline(Path(args.pv_bl))
    pv_pooled_df = load_pv_pooled(args.pv_pooled)
    per_run_df   = load_per_run(args.per_run)
    out_dir      = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    thread_ids = get_thread_ids(summary_df)
    print(f"Threads found: {thread_ids}")

    # Build aggregate "all" rows
    all_rows   = build_all_rows(summary_df, thread_ids)
    combined   = pd.concat([summary_df, all_rows], ignore_index=True)

    if pv_pooled_df is not None:
        print(f"Pooled p-values: {len(pv_pooled_df)} rows")
    else:
        print("WARNING: pooled p-value file not found; falling back to per-thread file.")

    print("\nGenerating 6 panel PDFs + legend …")
    for stem, metric, ylabel, _ in PANELS:
        save_panel(stem, metric, ylabel, combined, pv_df, pv_pooled_df, per_run_df, out_dir)

    save_legend(out_dir)

    print(f"\nDone. Files written to '{out_dir}/'")
if __name__ == "__main__":
    main()