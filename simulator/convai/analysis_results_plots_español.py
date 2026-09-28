"""
analysis_results_plots.py

Generates analysis plots for convai simulation results.

Reads CSVs produced by analyze_simulations.py:
  --summary    results.csv
  --pv_bl      results_pvalues_variant_vs_baseline.csv   (per-thread, kept for
               compatibility but STARS now come from --pv_pooled)
  --pv_pooled  results_pvalues_pooled.csv                (NEW: pooled across
               threads; columns: variant, config, metric, n, mean_delta,
               p_wilcoxon, sig_label)
  --per_run    results_per_run.csv   (optional, for scatter/jitter)

Plot suite:
  transitions/    - Δ% vs baseline for the 4 key transitions, per thread + all
  outcomes/       - % infected & vaccinated from susceptibles, absolute + Δ
  effectiveness/  - Vaccination effectiveness from susceptibles
  llm_behaviour/  - Message rate (msgs/cycle) and total_messages vs max_cycles scatter

Each plot:
  - Pink (#FF2D8B) = 600,  Green (#00E676) = 600_llm
  - Hatching for colorblind accessibility
  - Individual run points shown as jitter when per_run CSV is available
  - Significance stars from POOLED p-values (--pv_pooled)
  - All text labels (titles, axes, legends) are in Spanish for the thesis
  - A single shared legend is saved separately as legend.pdf; individual
    plots (except llm_behaviour) do not carry their own legend.

Usage:
  python analysis_results_plots.py \\
      --summary    convai/results.csv \\
      --pv_pooled  convai/results_pvalues_pooled.csv \\
      --per_run    convai/results_per_run.csv \\
      --out_dir    convai/tesis_figs/

  # Optional legacy arg (no longer drives stars):
      --pv_bl      convai/results_pvalues_variant_vs_baseline.csv
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

# -- Colours & styles ----------------------------------------------------------
COLOUR  = {"600": "#FF2D8B", "600_llm": "#00E676"}
HATCH   = {"600": "///",     "600_llm": "..."}
VARIANT_LABEL = {"600": "NeSy", "600_llm": "Solo-LLM"}

CAUTIOUS_SUFFIXES  = ["25pct_cautious",  "50pct_cautious",  "75pct_cautious"]
CREDULOUS_SUFFIXES = ["25pct_credulous", "50pct_credulous", "75pct_credulous"]
ALL_SUFFIXES       = CAUTIOUS_SUFFIXES + CREDULOUS_SUFFIXES

CASE_LABELS = {
    "baseline":         "Línea base",
    "25pct_cautious":   "Caut 25%",
    "50pct_cautious":   "Caut 50%",
    "75pct_cautious":   "Caut 75%",
    "25pct_credulous":  "Créd 25%",
    "50pct_credulous":  "Créd 50%",
    "75pct_credulous":  "Créd 75%",
}


def pct_only_label(suf: str) -> str:
    """Extract just the percentage from a suffix like '25pct_cautious' -> '25%'.

    Used inside two-panel (Cautelosos / Crédulos) figures, where the panel
    title already states which group it is, so the x-tick labels only need
    the number.
    """
    m = re.match(r"(\d+)pct", str(suf))
    if m:
        return f"{m.group(1)}%"
    return CASE_LABELS.get(suf, str(suf))


KEY_TRANSITIONS = [
    "trans_neutral_to_infected",
    "trans_neutral_to_vaccinated",
    "trans_infected_to_vaccinated",
    "trans_vaccinated_to_infected",
]
TRANS_LABELS = {
    "trans_neutral_to_infected":   "Neutral → Infectado",
    "trans_neutral_to_vaccinated": "Neutral → Vacunado",
    "trans_infected_to_vaccinated":"Infectado → Vacunado",
    "trans_vaccinated_to_infected":"Vacunado → Infectado",
}
TRANS_EXPECTED = {
    # (cautious_direction, credulous_direction)  +1=up, -1=down
    "trans_neutral_to_infected":   (-1, +1),
    "trans_neutral_to_vaccinated": (+1, -1),
    "trans_infected_to_vaccinated":(+1, -1),
    "trans_vaccinated_to_infected":(-1, +1),
}

OUTCOME_METRICS = [
    "pct_infected_susc",
    "pct_vaccinated_susc",
    "vax_effectiveness_susc",
]
OUTCOME_LABELS = {
    "pct_infected_susc":      "% Infectados (de susceptibles)",
    "pct_vaccinated_susc":    "% Vacunados (de susceptibles)",
    "vax_effectiveness_susc": "Efectividad de vacunación (de susceptibles)",
}
# Shorter versions used on y-axis labels to avoid repetition with the title
OUTCOME_YLABEL = {
    "pct_infected_susc":      "% Infectados",
    "pct_vaccinated_susc":    "% Vacunados",
    "vax_effectiveness_susc": "% Efectividad de vacunación",
}
# Short transition labels for y-axis (full label goes in suptitle)
TRANS_YLABEL = {
    "trans_neutral_to_infected":   "Δ % Neutral→Infectado",
    "trans_neutral_to_vaccinated": "Δ % Neutral→Vacunado",
    "trans_infected_to_vaccinated":"Δ % Infectado→Vacunado",
    "trans_vaccinated_to_infected":"Δ % Vacunado→Infectado",
}

# Group labels used in the two-panel (cautious/credulous) figures
GROUP_LABELS = {
    "Cautious":  "Cautelosos",
    "Credulous": "Crédulos",
}

STAR_THRESHOLDS = [(0.001, "***"), (0.01, "**"), (0.05, "*"), (1.0, "ns")]

# -- Font sizes (single source of truth) --------------------------------------
# Bumped up across the board (including significance stars) for better
# legibility once the figures are placed in the document.
FS_BASE       = 14   # rcParams default
FS_TITLE      = 15   # axes title
FS_SUPTITLE   = 16   # figure suptitle
FS_AXLABEL    = 14   # x/y axis labels
FS_TICK       = 13   # tick labels
FS_LEGEND     = 13   # legend text
FS_ANNOT      = 15   # significance stars
FS_CBAR       = 13   # colorbar label / tick labels

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
    "font.size":        FS_BASE,
    "axes.titlesize":   FS_TITLE,
    "axes.labelsize":   FS_AXLABEL,
    "xtick.labelsize":  FS_TICK,
    "ytick.labelsize":  FS_TICK,
    "legend.fontsize":  FS_LEGEND,
    "figure.titlesize": FS_SUPTITLE,
})

# -- Significance --------------------------------------------------------------

def stars(p) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    for thr, lbl in STAR_THRESHOLDS:
        if p < thr:
            return lbl
    return ""   # "ns" omitted for clean plots; annotate only significant results


def annotate_bar(ax, x, bar_value, error, label, fontsize=FS_ANNOT):
    """
    Place significance label at the *outer* end of the bar:
      - positive bar  → above  the top  (bar_value + error + small gap)
      - negative bar  → below  the bottom (bar_value - error - small gap)
    """
    if not label:
        return
    # Determine a sensible gap relative to the axis range
    ylim = ax.get_ylim()
    axis_span = max(abs(ylim[1] - ylim[0]), 1e-6)
    gap = axis_span * 0.012

    if bar_value >= 0:
        y   = bar_value + error + gap
        va  = "bottom"
    else:
        y   = bar_value - error - gap
        va  = "top"

    ax.text(x, y, label, ha="center", va=va, fontsize=fontsize,
            fontweight="bold", color="#222222")


# -- CSV loading ---------------------------------------------------------------

def load_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["variant"].isin(["600", "600_llm"])].copy()
    df["variant"] = df["variant"].astype(str)
    return df


def load_pv_baseline(path: Path) -> pd.DataFrame:
    """Legacy per-thread p-value file (kept for compatibility)."""
    df = pd.read_csv(path)
    df["variant"] = df["variant"].astype(str)
    return df


def load_pv_pooled(path: Path | None) -> pd.DataFrame | None:
    """
    Pooled p-value file.  Expected columns:
        variant, config, metric, n, mean_delta, p_wilcoxon, sig_label

    'config' holds values like '25pct_cautious', '50pct_credulous', etc.
    (no thread_id column - pooled across all threads).
    """
    if path is None or not path.exists():
        return None
    df = pd.read_csv(path)
    df["variant"] = df["variant"].astype(str)
    return df


def load_per_run(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.exists():
        return None
    df = pd.read_csv(path)
    df["variant"] = df["variant"].astype(str)
    return df


def get_thread_ids(summary_df: pd.DataFrame) -> list[str]:
    tcs = summary_df["thread_config"].astype(str).unique()
    return sorted(tc for tc in tcs if re.fullmatch(r"\d+", tc))


# -- Data extraction -----------------------------------------------------------

def get_mean_std(summary_df: pd.DataFrame, variant: str, tc: str, metric: str):
    row = summary_df[(summary_df["variant"] == variant) &
                     (summary_df["thread_config"].astype(str) == tc)]
    if row.empty:
        return None, 0.0
    return row.iloc[0].get(f"{metric}_mean"), row.iloc[0].get(f"{metric}_std", 0.0)


# -- P-value lookups -----------------------------------------------------------

def get_pv(pv_df: pd.DataFrame, variant: str, thread_id: str, config: str, metric: str):
    """Legacy per-thread lookup (used only when no pooled file is available)."""
    row = pv_df[
        (pv_df["variant"]   == variant) &
        (pv_df["thread_id"].astype(str) == str(thread_id)) &
        (pv_df["config"]    == config) &
        (pv_df["metric"]    == metric)
    ]
    if row.empty:
        return None
    return row.iloc[0]["p_value"]


def get_pv_pooled(pv_pooled_df: pd.DataFrame | None,
                  variant: str, config: str, metric: str) -> float | None:
    """
    Look up a pooled p-value.

    The pooled CSV has columns: variant, config, metric, p_wilcoxon (and others).
    'config' stores the condition suffix, e.g. '25pct_cautious'.
    """
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
    """
    Return the best available p-value:
      1. Pooled file (preferred, thread-agnostic).
      2. Legacy per-thread file (fallback).
    """
    p = get_pv_pooled(pv_pooled_df, variant, config, metric)
    if p is not None:
        return p
    return get_pv(pv_df, variant, thread_id, config, metric)


def get_run_vals(per_run_df: pd.DataFrame | None, variant: str, tc: str, metric: str) -> list:
    if per_run_df is None:
        return []
    sub = per_run_df[(per_run_df["variant"] == variant) &
                     (per_run_df["thread_config"].astype(str) == tc)]
    vals = sub[metric].dropna().tolist()
    return vals


# -- Legend ---------------------------------------------------------------

def add_legend(fig, extra_patches=None, y=0.025):
    """
    Attach a single horizontal legend to the *figure*, centred below all axes.
    Call this after tight_layout / subplots_adjust so the bbox is stable.

    `y` controls the vertical anchor (in figure fraction) - raise it to move
    the legend closer to the plot.
    """
    handles = []
    for v in ["600", "600_llm"]:
        handles.append(mpatches.Patch(
            facecolor=COLOUR[v], hatch=HATCH[v], edgecolor="#333333",
            alpha=0.85, label=VARIANT_LABEL[v]
        ))
    if extra_patches:
        handles += extra_patches
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, y),
        ncol=len(handles),
        fontsize=FS_LEGEND,
        framealpha=0.7,
        edgecolor="#aaaaaa",
    )


def save_standalone_legend(out_dir: Path):
    """
    Render the shared variant legend (NeSy / Solo-LLM) on its own, and save
    it as a single separate PDF ('legend.pdf'). Individual figures no longer
    carry their own legend (except llm_behaviour/, which keeps its own).
    """
    handles = []
    for v in ["600", "600_llm"]:
        handles.append(mpatches.Patch(
            facecolor=COLOUR[v], hatch=HATCH[v], edgecolor="#333333",
            alpha=0.85, label=VARIANT_LABEL[v]
        ))
    fig = plt.figure(figsize=(4, 0.6))
    fig.legend(
        handles=handles,
        loc="center",
        ncol=len(handles),
        fontsize=FS_LEGEND,
        framealpha=0.7,
        edgecolor="#aaaaaa",
    )
    fname = "legend.pdf"
    fig.savefig(out_dir / fname, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  guardado {fname}")


# -- Generic grouped bar (absolute values) ------------------------------------

def plot_grouped_bars(ax, configs, summary_df, thread_id, metric,
                      pv_df, pv_pooled_df, ylabel, title, per_run_df=None,
                      show_ylabel=True, show_title=False, ylim=None,
                      show_stars=True):
    """
    Side-by-side bars (600 | 600_llm) for each config.
    configs: list of suffix strings (e.g. ['baseline','25pct_cautious',...])
    Stars come from pooled p-values when available, unless show_stars=False
    (e.g. for messages_per_cycle, which isn't a hypothesis-tested metric).

    `ylim`, if given, is applied to the axis *before* the significance stars
    are placed, so the star offset (which depends on the axis span) is
    computed against the final scale.
    """
    bar_w = 0.35
    x     = np.arange(len(configs))

    for vi, variant in enumerate(["600", "600_llm"]):
        offset = (vi - 0.5) * bar_w
        ys, es = [], []
        for cfg in configs:
            tc = thread_id if cfg == "baseline" else f"{thread_id}_{cfg}"
            m, s = get_mean_std(summary_df, variant, tc, metric)
            ys.append(m or 0.0)
            es.append(s or 0.0)

        ax.bar(x + offset, ys, bar_w,
               color=COLOUR[variant], hatch=HATCH[variant],
               edgecolor="#333333", linewidth=0.6,
               alpha=0.85, label=VARIANT_LABEL[variant],
               yerr=es, capsize=3,
               error_kw={"elinewidth": 0.8, "ecolor": "#555555"})

        # Jitter individual run points
        if per_run_df is not None:
            for ci, cfg in enumerate(configs):
                tc = thread_id if cfg == "baseline" else f"{thread_id}_{cfg}"
                vals = get_run_vals(per_run_df, variant, tc, metric)
                if vals:
                    jx = np.random.normal(x[ci] + offset, 0.04, size=len(vals))
                    ax.scatter(jx, vals, color="black", s=14, zorder=5,
                               alpha=0.7, linewidths=0)

        if ylim is not None:
            ax.set_ylim(*ylim)

        # Significance stars at outer end of bar (vs baseline) - pooled p-values
        if show_stars:
            for ci, cfg in enumerate(configs):
                if cfg == "baseline":
                    continue
                p = resolve_pv(pv_pooled_df, pv_df, variant, thread_id, cfg, metric)
                s = stars(p)
                if s:
                    annotate_bar(ax, x[ci] + offset, ys[ci], es[ci], s)

    ax.set_xticks(x)
    ax.set_xticklabels([CASE_LABELS.get(c, c) for c in configs],
                       fontsize=FS_TICK, rotation=20, ha="right")
    if show_ylabel:
        ax.set_ylabel(ylabel, fontsize=FS_AXLABEL)
    else:
        ax.set_ylabel("")
        ax.tick_params(labelleft=False)
    if show_title and title:
        ax.set_title(title, fontsize=FS_TITLE, pad=5)
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    if ylim is not None:
        ax.set_ylim(*ylim)


def compute_abs_extent(configs, summary_df, thread_id, metric):
    """
    Compute the (min, max) extent (bar value ± error) that plot_grouped_bars
    would need for this thread/metric, without drawing anything. Used to
    work out a shared y-axis scale across several figures of the same
    metric (e.g. one per thread).
    """
    lo, hi = 0.0, 0.0
    for variant in ["600", "600_llm"]:
        for cfg in configs:
            tc = thread_id if cfg == "baseline" else f"{thread_id}_{cfg}"
            m, s = get_mean_std(summary_df, variant, tc, metric)
            m = m or 0.0
            s = s or 0.0
            lo = min(lo, m - s)
            hi = max(hi, m + s)
    return lo, hi


# -- Delta vs baseline bar -----------------------------------------------------

def compute_delta_extent(suffixes, summary_df, thread_id, metric, pv_df, pv_pooled_df):
    """
    Compute the (min, max) extent (bar value ± error) that plot_delta_bars
    would need for this thread/metric/suffix-group, without drawing
    anything. Used to work out a shared y-axis scale across several figures.
    """
    lo, hi = 0.0, 0.0
    for variant in ["600", "600_llm"]:
        tc_bl = thread_id
        bl_m, bl_s = get_mean_std(summary_df, variant, tc_bl, metric)
        bl_m = bl_m or 0.0
        for suf in suffixes:
            tc = f"{thread_id}_{suf}"
            m, s = get_mean_std(summary_df, variant, tc, metric)
            val = (m or 0.0) - bl_m
            err = np.sqrt((s or 0.0) ** 2 + (bl_s or 0.0) ** 2)
            lo = min(lo, val - err)
            hi = max(hi, val + err)
    return lo, hi


def plot_delta_bars(ax, suffixes, summary_df, thread_id, metric,
                    pv_df, pv_pooled_df, ylabel, title, per_run_df=None,
                    show_ylabel=True, ylim=None):
    """
    Δ vs baseline bars for each non-baseline suffix.
    Stars come from pooled p-values when available.

    `title` here is the small panel label (e.g. "Cautelosos" / "Crédulos"),
    which is kept so the reader knows which group the panel refers to; since
    it's shown, the x-tick labels below only need the bare percentage.

    `ylim`, if given, is applied to the axis *before* the significance stars
    are placed, so the star offset (which depends on the axis span) is
    computed against the final, shared scale rather than the autoscaled one.
    """
    bar_w = 0.35
    x     = np.arange(len(suffixes))

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
            # propagate error in quadrature
            es.append(np.sqrt((s or 0.0) ** 2 + (bl_s or 0.0) ** 2))

        ax.bar(x + offset, ys, bar_w,
               color=COLOUR[variant], hatch=HATCH[variant],
               edgecolor="#333333", linewidth=0.6,
               alpha=0.85, label=VARIANT_LABEL[variant],
               yerr=es, capsize=3,
               error_kw={"elinewidth": 0.8, "ecolor": "#555555"})

        # Jitter deltas from individual runs
        if per_run_df is not None:
            bl_vals = get_run_vals(per_run_df, variant, tc_bl, metric)
            bl_mean_run = float(np.mean(bl_vals)) if bl_vals else bl_m
            for ci, suf in enumerate(suffixes):
                tc = f"{thread_id}_{suf}"
                vals = get_run_vals(per_run_df, variant, tc, metric)
                if vals:
                    deltas = [v - bl_mean_run for v in vals]
                    jx = np.random.normal(x[ci] + offset, 0.04, size=len(deltas))
                    ax.scatter(jx, deltas, color="black", s=14, zorder=5,
                               alpha=0.7, linewidths=0)

        if ylim is not None:
            ax.set_ylim(*ylim)

        # Stars at outer end of bar - pooled p-values
        for ci, suf in enumerate(suffixes):
            p = resolve_pv(pv_pooled_df, pv_df, variant, thread_id, suf, metric)
            s = stars(p)
            if s:
                annotate_bar(ax, x[ci] + offset, ys[ci], es[ci], s)

    ax.axhline(0, color="#333333", linewidth=0.9, linestyle="--", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([pct_only_label(s) for s in suffixes],
                       fontsize=FS_TICK, rotation=0, ha="center")
    if show_ylabel:
        ax.set_ylabel(ylabel, fontsize=FS_AXLABEL)
    else:
        ax.set_ylabel("")
        ax.tick_params(labelleft=False)
    ax.set_title(title, fontsize=FS_TITLE, pad=5)
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    if ylim is not None:
        ax.set_ylim(*ylim)


# -- Thread label helper -------------------------------------------------------

THREAD_LABELS = {
    "524922729485848576": "Hilo A (108 susc.)",
    "524949443607412737": "Hilo B (236 susc.)",
    "524990163446140928": "Hilo C (494 susc.)",
    "all": "Todos los hilos (promedio)",
}

def tlabel(tid):
    return THREAD_LABELS.get(str(tid), str(tid))


# -- Build "all threads" aggregate rows ----------------------------------------

def build_all_rows(summary_df: pd.DataFrame, thread_ids: list[str]) -> pd.DataFrame:
    """
    Create synthetic rows for thread_id='all' / 'all_<suffix>' by averaging
    per-thread means and propagating std.
    """
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


# ════════════════════════════════════════════════════════════════════════════
# Plot generators
# ════════════════════════════════════════════════════════════════════════════

# -- 1. Transition Δ% plots ----------------------------------------------------

def make_transition_plots(summary_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df=None):
    trans_dir = out_dir / "transitions"
    trans_dir.mkdir(parents=True, exist_ok=True)

    for metric in KEY_TRANSITIONS:
        # First pass: scan every thread + suffix-group for this metric so
        # all of its figures share one y-axis scale and are comparable.
        global_lo, global_hi = 0.0, 0.0
        for tid in thread_ids + ["all"]:
            thread_id = "all" if tid == "all" else str(tid)
            for suffixes in (CAUTIOUS_SUFFIXES, CREDULOUS_SUFFIXES):
                lo, hi = compute_delta_extent(
                    suffixes, summary_df, thread_id, metric, pv_df, pv_pooled_df
                )
                global_lo = min(global_lo, lo)
                global_hi = max(global_hi, hi)

        pad = 0.15 * max(global_hi - global_lo, 1e-6)
        shared_ylim = (global_lo - pad, global_hi + pad)

        for tid in thread_ids + ["all"]:
            fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)

            for i, (ax, (group_name, suffixes)) in enumerate(zip(
                axes, [("Cautious", CAUTIOUS_SUFFIXES), ("Credulous", CREDULOUS_SUFFIXES)]
            )):
                thread_id = "all" if tid == "all" else str(tid)
                plot_delta_bars(
                    ax, suffixes, summary_df, thread_id, metric,
                    pv_df, pv_pooled_df,
                    ylabel=TRANS_YLABEL[metric],
                    title=GROUP_LABELS[group_name],
                    per_run_df=per_run_df,
                    show_ylabel=(i == 0),
                    ylim=shared_ylim,
                )

            fig.tight_layout(rect=[0, 0.02, 1, 1])

            fname = f"{tid}_{metric}.pdf"
            fig.savefig(trans_dir / fname, format="pdf", bbox_inches="tight")
            plt.close(fig)
            print(f"  guardado transitions/{fname}")


# -- 2. Outcome plots (absolute + delta) --------------------------------------

def make_outcome_plots(summary_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df=None):
    out_dir2 = out_dir / "outcomes"
    out_dir2.mkdir(parents=True, exist_ok=True)

    configs_all = ["baseline"] + ALL_SUFFIXES

    for metric in OUTCOME_METRICS:
        label = OUTCOME_LABELS[metric]

        # pct_infected_susc / pct_vaccinated_susc are true percentages of a
        # population, always within [0, 100], so they get the fixed full
        # scale. vax_effectiveness_susc is a ratio that can go negative or
        # exceed 100, so instead it gets a shared scale computed from the
        # actual data across all threads (still consistent across figures).
        if metric == "vax_effectiveness_susc":
            global_lo, global_hi = 0.0, 0.0
            for tid in thread_ids + ["all"]:
                thread_id = "all" if tid == "all" else str(tid)
                lo, hi = compute_abs_extent(configs_all, summary_df, thread_id, metric)
                global_lo = min(global_lo, lo)
                global_hi = max(global_hi, hi)
            pad = 0.08 * max(global_hi - global_lo, 1e-6)
            abs_ylim = (global_lo - pad, global_hi + pad)
        else:
            abs_ylim = (0, 100)

        # Shared y-axis scale for the delta panels of this metric, across
        # all threads (mirrors the fixed treatment done for `transitions`).
        global_lo, global_hi = 0.0, 0.0
        for tid in thread_ids + ["all"]:
            thread_id = "all" if tid == "all" else str(tid)
            for suffixes in (CAUTIOUS_SUFFIXES, CREDULOUS_SUFFIXES):
                lo, hi = compute_delta_extent(
                    suffixes, summary_df, thread_id, metric, pv_df, pv_pooled_df
                )
                global_lo = min(global_lo, lo)
                global_hi = max(global_hi, hi)
        pad = 0.15 * max(global_hi - global_lo, 1e-6)
        delta_ylim = (global_lo - pad, global_hi + pad)

        for tid in thread_ids + ["all"]:
            thread_id = "all" if tid == "all" else str(tid)

            # Absolute values: all 7 configs side by side, shared scale
            # across threads for this metric, and a slightly shorter figure.
            fig, ax = plt.subplots(figsize=(11, 4.5))
            plot_grouped_bars(
                ax, configs_all, summary_df, thread_id, metric,
                pv_df, pv_pooled_df, ylabel=OUTCOME_YLABEL[metric],
                title=f"{label}  -  {tlabel(tid)}  (absoluto)",
                per_run_df=per_run_df,
                show_title=False,
                ylim=abs_ylim,
            )
            fig.tight_layout(rect=[0, 0.02, 1, 1])
            fname = f"{tid}_{metric}_abs.pdf"
            fig.savefig(out_dir2 / fname, format="pdf", bbox_inches="tight")
            plt.close(fig)
            print(f"  guardado outcomes/{fname}")

            # Delta: cautious + credulous side by side, shared y-axis scale
            # across threads for this metric so the delta figures are
            # comparable too.
            fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
            for i, (ax, (group_name, suffixes)) in enumerate(zip(
                axes, [("Cautious", CAUTIOUS_SUFFIXES), ("Credulous", CREDULOUS_SUFFIXES)]
            )):
                plot_delta_bars(
                    ax, suffixes, summary_df, thread_id, metric,
                    pv_df, pv_pooled_df,
                    ylabel=f"Δ {OUTCOME_YLABEL[metric]}",
                    title=GROUP_LABELS[group_name],
                    per_run_df=per_run_df,
                    show_ylabel=(i == 0),
                    ylim=delta_ylim,
                )
            fig.tight_layout(rect=[0, 0.02, 1, 1])
            fname = f"{tid}_{metric}_delta.pdf"
            fig.savefig(out_dir2 / fname, format="pdf", bbox_inches="tight")
            plt.close(fig)
            print(f"  guardado outcomes/{fname}")

def make_llm_behaviour_plots(summary_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df=None):
    llm_dir = out_dir / "llm_behaviour"
    llm_dir.mkdir(parents=True, exist_ok=True)

    configs_all = ["baseline"] + ALL_SUFFIXES

    # 4a. Messages per cycle - absolute, all cases (no legend; the shared
    # legend.pdf covers the variant colours). Shared y-axis scale across
    # threads so the figures are comparable.
    global_lo, global_hi = 0.0, 0.0
    for tid in thread_ids + ["all"]:
        thread_id = "all" if tid == "all" else str(tid)
        lo, hi = compute_abs_extent(configs_all, summary_df, thread_id, "messages_per_cycle")
        global_lo = min(global_lo, lo)
        global_hi = max(global_hi, hi)
    pad = 0.08 * max(global_hi - global_lo, 1e-6)
    mpc_ylim = (global_lo - pad, global_hi + pad)

    for tid in thread_ids + ["all"]:
        thread_id = "all" if tid == "all" else str(tid)
        fig, ax = plt.subplots(figsize=(11, 5.5))
        plot_grouped_bars(
            ax, configs_all, summary_df, thread_id, "messages_per_cycle",
            pv_df, pv_pooled_df, ylabel="Mensajes / ciclo",
            title=f"Mensajes por ciclo  -  {tlabel(tid)}",
            per_run_df=per_run_df,
            show_title=False,
            ylim=mpc_ylim,
            show_stars=False,
        )
        fig.tight_layout(rect=[0, 0.02, 1, 1])
        fname = f"{tid}_messages_per_cycle.pdf"
        fig.savefig(llm_dir / fname, format="pdf", bbox_inches="tight")
        plt.close(fig)
        print(f"  guardado llm_behaviour/{fname}")

    # 4b. Total messages vs max_cycles scatter - all threads in one plot
    if per_run_df is not None:
        THREAD_MARKERS = {
            thread_ids[0]: "o",
            thread_ids[1]: "s",
            thread_ids[2]: "^",
        }

        fig, ax = plt.subplots(figsize=(8, 5.5))

        for variant in ["600", "600_llm"]:
            for tid in thread_ids:
                thread_id = str(tid)
                marker = THREAD_MARKERS.get(thread_id, "D")

                sub = per_run_df[
                    (per_run_df["variant"] == variant) &
                    (per_run_df["thread_config"].astype(str).str.startswith(thread_id))
                ]
                if sub.empty:
                    continue

                ax.scatter(
                    sub["max_cycles"], sub["total_messages"],
                    color=COLOUR[variant], alpha=0.75, s=45,
                    marker=marker,
                    edgecolors="#333333", linewidths=0.5,
                )

        # Build legend: variant patches + thread markers (kept, moved up)
        variant_patches = [
            mpatches.Patch(facecolor=COLOUR[v], edgecolor="#333333",
                           alpha=0.85, label=VARIANT_LABEL[v])
            for v in ["600", "600_llm"]
        ]
        thread_handles = [
            plt.Line2D([0], [0], marker=THREAD_MARKERS.get(str(tid), "D"),
                       color="none", markerfacecolor="#888888",
                       markeredgecolor="#333333", markersize=7,
                       label=tlabel(tid))
            for tid in thread_ids
        ]

        ax.set_xlabel("Ciclos máximos", fontsize=FS_AXLABEL)
        ax.set_ylabel("Mensajes totales", fontsize=FS_AXLABEL)
        ax.tick_params(labelsize=FS_TICK)
        ax.yaxis.grid(True)
        ax.spines[["top", "right"]].set_visible(False)

        fig.tight_layout(rect=[0, 0.16, 1, 1])
        fig.legend(
            handles=variant_patches + thread_handles,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.02),
            ncol=len(variant_patches + thread_handles),
            fontsize=FS_LEGEND,
            framealpha=0.7,
            edgecolor="#aaaaaa",
        )

        fname = "all_scatter_messages_vs_cycles.pdf"
        fig.savefig(llm_dir / fname, format="pdf", bbox_inches="tight")
        plt.close(fig)
        print(f"  guardado llm_behaviour/{fname}")

# -- Main ----------------------------------------------------------------------

def main():
    np.random.seed(42)  # reproducible jitter

    parser = argparse.ArgumentParser()
    parser.add_argument("--summary",    default="convai/results.csv")
    parser.add_argument("--pv_bl",      default="convai/results_pvalues_variant_vs_baseline.csv",
                        help="Legacy per-thread p-value file (fallback only).")
    parser.add_argument("--pv_pooled",  default="convai/results_pooled_delta.csv",
                        help="Pooled p-value file (variant, config, metric, p_wilcoxon). "
                             "Stars in all plots come from this file when provided.")
    parser.add_argument("--per_run",    default="convai/results_per_run.csv")
    parser.add_argument("--out_dir",    default="convai/tesis_figs")
    args = parser.parse_args()

    summary_df    = load_summary(Path(args.summary))
    pv_df         = load_pv_baseline(Path(args.pv_bl))
    pv_pooled_df  = load_pv_pooled(Path(args.pv_pooled))
    per_run_df    = load_per_run(Path(args.per_run))
    out_dir       = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if pv_pooled_df is not None:
        print(f"P-values agrupados cargados: {len(pv_pooled_df)} filas desde '{args.pv_pooled}'")
    else:
        print(f"ADVERTENCIA: no se encontró el archivo de p-values agrupados en '{args.pv_pooled}'. "
              "Usando el archivo por hilo como respaldo para las estrellas de significancia.")

    thread_ids = get_thread_ids(summary_df)
    print(f"Hilos encontrados: {thread_ids}")

    # Build and merge "all threads" aggregate rows
    all_rows = build_all_rows(summary_df, thread_ids)
    combined_df = pd.concat([summary_df, all_rows], ignore_index=True)

    print("\n-- Leyenda compartida --")
    save_standalone_legend(out_dir)

    print("\n-- Gráficos de Δ% de transiciones --")
    make_transition_plots(combined_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df)

    print("\n-- Gráficos de resultados (outcomes) --")
    make_outcome_plots(combined_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df)

    print("\n-- Gráficos de comportamiento del LLM --")
    make_llm_behaviour_plots(combined_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df)

    print(f"\nListo. Todos los gráficos se guardaron en '{out_dir}/'")
    print("\nEstructura de salida:")
    print("  legend.pdf    - leyenda compartida (NeSy / Solo-LLM) para usar en el documento")
    print("  transitions/  - Δ% de cada una de las 4 transiciones clave, por hilo + todos")
    print("  outcomes/     - % infectados/vacunados/efectividad, absoluto + delta")
    print("  llm_behaviour/- gráficos de mensajes/ciclo + dispersión mensajes totales vs ciclos máximos")


if __name__ == "__main__":
    main()