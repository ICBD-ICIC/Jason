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

Usage:
  python analysis_results_plots.py \\
      --summary    convai/results.csv \\
      --pv_pooled  convai/results_pvalues_pooled.csv \\
      --per_run    convai/results_per_run.csv \\
      --out_dir    convai/plots/

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
VARIANT_LABEL = {"600": "600", "600_llm": "600-LLM"}

CAUTIOUS_SUFFIXES  = ["25pct_cautious",  "50pct_cautious",  "75pct_cautious"]
CREDULOUS_SUFFIXES = ["25pct_credulous", "50pct_credulous", "75pct_credulous"]
ALL_SUFFIXES       = CAUTIOUS_SUFFIXES + CREDULOUS_SUFFIXES

CASE_LABELS = {
    "baseline":         "Baseline",
    "25pct_cautious":   "Caut 25%",
    "50pct_cautious":   "Caut 50%",
    "75pct_cautious":   "Caut 75%",
    "25pct_credulous":  "Cred 25%",
    "50pct_credulous":  "Cred 50%",
    "75pct_credulous":  "Cred 75%",
}

KEY_TRANSITIONS = [
    "trans_neutral_to_infected",
    "trans_neutral_to_vaccinated",
    "trans_infected_to_vaccinated",
    "trans_vaccinated_to_infected",
]
TRANS_LABELS = {
    "trans_neutral_to_infected":   "Neutral → Infected",
    "trans_neutral_to_vaccinated": "Neutral → Vaccinated",
    "trans_infected_to_vaccinated":"Infected → Vaccinated",
    "trans_vaccinated_to_infected":"Vaccinated → Infected",
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
    "pct_infected_susc":      "% Infected (of susceptibles)",
    "pct_vaccinated_susc":    "% Vaccinated (of susceptibles)",
    "vax_effectiveness_susc": "Vaccination Effectiveness (of susceptibles)",
}
# Shorter versions used on y-axis labels to avoid repetition with the title
OUTCOME_YLABEL = {
    "pct_infected_susc":      "% Infected",
    "pct_vaccinated_susc":    "% Vaccinated",
    "vax_effectiveness_susc": "% Vaccination Effectiveness",
}
# Short transition labels for y-axis (full label goes in suptitle)
TRANS_YLABEL = {
    "trans_neutral_to_infected":   "Δ % Neutral→Infected",
    "trans_neutral_to_vaccinated": "Δ % Neutral→Vaccinated",
    "trans_infected_to_vaccinated":"Δ % Infected→Vaccinated",
    "trans_vaccinated_to_infected":"Δ % Vaccinated→Infected",
}

STAR_THRESHOLDS = [(0.001, "***"), (0.01, "**"), (0.05, "*"), (1.0, "ns")]

# -- Font sizes (single source of truth) --------------------------------------
FS_BASE       = 16   # rcParams default
FS_TITLE      = 16   # axes title
FS_SUPTITLE   = 16   # figure suptitle
FS_AXLABEL    = 16   # x/y axis labels
FS_TICK       = 16   # tick labels
FS_LEGEND     = 16   # legend text
FS_ANNOT      = 16   # significance stars
FS_CBAR       = 16   # colorbar label / tick labels

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
    gap = axis_span * 0.025

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


# -- Legend (bottom, outside, horizontal) -------------------------------------

def add_legend(fig, extra_patches=None):
    """
    Attach a single horizontal legend to the *figure*, centred below all axes.
    Call this after tight_layout / subplots_adjust so the bbox is stable.
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
        bbox_to_anchor=(0.5, 0.025),
        ncol=len(handles),
        fontsize=FS_LEGEND,
        framealpha=0.7,
        edgecolor="#aaaaaa",
    )


# -- Generic grouped bar (absolute values) ------------------------------------

def plot_grouped_bars(ax, configs, summary_df, thread_id, metric,
                      pv_df, pv_pooled_df, ylabel, title, per_run_df=None,
                      show_ylabel=True):
    """
    Side-by-side bars (600 | 600_llm) for each config.
    configs: list of suffix strings (e.g. ['baseline','25pct_cautious',...])
    Stars come from pooled p-values when available.
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

        # Significance stars at outer end of bar (vs baseline) - pooled p-values
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
    ax.set_title(title, fontsize=FS_TITLE, pad=5)
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


# -- Delta vs baseline bar -----------------------------------------------------

def plot_delta_bars(ax, suffixes, summary_df, thread_id, metric,
                    pv_df, pv_pooled_df, ylabel, title, per_run_df=None,
                    show_ylabel=True):
    """
    Δ vs baseline bars for each non-baseline suffix.
    Stars come from pooled p-values when available.
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

        # Stars at outer end of bar - pooled p-values
        for ci, suf in enumerate(suffixes):
            p = resolve_pv(pv_pooled_df, pv_df, variant, thread_id, suf, metric)
            s = stars(p)
            if s:
                annotate_bar(ax, x[ci] + offset, ys[ci], es[ci], s)

    ax.axhline(0, color="#333333", linewidth=0.9, linestyle="--", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([CASE_LABELS.get(s, s) for s in suffixes],
                       fontsize=FS_TICK, rotation=20, ha="right")
    if show_ylabel:
        ax.set_ylabel(ylabel, fontsize=FS_AXLABEL)
    else:
        ax.set_ylabel("")
        ax.tick_params(labelleft=False)
    ax.set_title(title, fontsize=FS_TITLE, pad=5)
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


# -- Thread label helper -------------------------------------------------------

THREAD_LABELS = {
    "524922729485848576": "Thread A (108 susc.)",
    "524949443607412737": "Thread B (236 susc.)",
    "524990163446140928": "Thread C (494 susc.)",
    "all": "All threads (mean)",
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
        metric_label = TRANS_LABELS[metric]
        caut_dir, cred_dir = TRANS_EXPECTED[metric]
        direction_note = (
            f"Expected: Cautious {'↓' if caut_dir < 0 else '↑'}  "
            f"Credulous {'↓' if cred_dir < 0 else '↑'}"
        )

        for tid in thread_ids + ["all"]:
            fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
            # FIX 2: reduced y and tighter rect top to close gap between
            # suptitle and subplot titles
            fig.suptitle(
                f"{metric_label}  -  {tlabel(tid)}\n{direction_note}",
                fontsize=FS_SUPTITLE, y=1.00
            )

            for i, (ax, (group_name, suffixes)) in enumerate(zip(
                axes, [("Cautious", CAUTIOUS_SUFFIXES), ("Credulous", CREDULOUS_SUFFIXES)]
            )):
                thread_id = "all" if tid == "all" else str(tid)
                plot_delta_bars(
                    ax, suffixes, summary_df, thread_id, metric,
                    pv_df, pv_pooled_df,
                    ylabel=TRANS_YLABEL[metric],
                    title=group_name,
                    per_run_df=per_run_df,
                    show_ylabel=(i == 0),
                )

            fig.tight_layout(rect=[0, 0.08, 1, 0.93])
            add_legend(fig)

            fname = f"{tid}_{metric}.pdf"
            fig.savefig(trans_dir / fname, format="pdf", bbox_inches="tight")
            plt.close(fig)
            print(f"  saved transitions/{fname}")


# -- 2. Outcome plots (absolute + delta) --------------------------------------

def make_outcome_plots(summary_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df=None):
    out_dir2 = out_dir / "outcomes"
    out_dir2.mkdir(parents=True, exist_ok=True)

    configs_all = ["baseline"] + ALL_SUFFIXES

    for metric in OUTCOME_METRICS:
        label = OUTCOME_LABELS[metric]

        for tid in thread_ids + ["all"]:
            thread_id = "all" if tid == "all" else str(tid)

            # Absolute values: all 7 configs side by side
            fig, ax = plt.subplots(figsize=(11, 5.5))
            plot_grouped_bars(
                ax, configs_all, summary_df, thread_id, metric,
                pv_df, pv_pooled_df, ylabel=OUTCOME_YLABEL[metric],
                title=f"{label}  -  {tlabel(tid)}  (absolute)",
                per_run_df=per_run_df,
            )
            fig.tight_layout(rect=[0, 0.08, 1, 1])
            add_legend(fig)
            fname = f"{tid}_{metric}_abs.pdf"
            fig.savefig(out_dir2 / fname, format="pdf", bbox_inches="tight")
            plt.close(fig)
            print(f"  saved outcomes/{fname}")

            # Delta: cautious + credulous side by side
            fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
            fig.suptitle(f"Δ {label}  -  {tlabel(tid)}", fontsize=FS_SUPTITLE, y=1.12)
            for i, (ax, (group_name, suffixes)) in enumerate(zip(
                axes, [("Cautious", CAUTIOUS_SUFFIXES), ("Credulous", CREDULOUS_SUFFIXES)]
            )):
                plot_delta_bars(
                    ax, suffixes, summary_df, thread_id, metric,
                    pv_df, pv_pooled_df,
                    ylabel=f"Δ {OUTCOME_YLABEL[metric]}",
                    title=group_name,
                    per_run_df=per_run_df,
                    show_ylabel=(i == 0),
                )
            fig.tight_layout(rect=[0, 0.08, 1, 1.2])
            add_legend(fig)
            fname = f"{tid}_{metric}_delta.pdf"
            fig.savefig(out_dir2 / fname, format="pdf", bbox_inches="tight")
            plt.close(fig)
            print(f"  saved outcomes/{fname}")

def make_llm_behaviour_plots(summary_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df=None):
    llm_dir = out_dir / "llm_behaviour"
    llm_dir.mkdir(parents=True, exist_ok=True)

    configs_all = ["baseline"] + ALL_SUFFIXES

    # 4a. Messages per cycle - absolute, all cases
    for tid in thread_ids + ["all"]:
        thread_id = "all" if tid == "all" else str(tid)
        fig, ax = plt.subplots(figsize=(11, 5.5))
        plot_grouped_bars(
            ax, configs_all, summary_df, thread_id, "messages_per_cycle",
            pv_df, pv_pooled_df, ylabel="Messages / cycle",
            title=f"Messages per cycle  -  {tlabel(tid)}",
            per_run_df=per_run_df,
        )
        fig.tight_layout(rect=[0, 0.08, 1, 1])
        add_legend(fig)
        fname = f"{tid}_messages_per_cycle.pdf"
        fig.savefig(llm_dir / fname, format="pdf", bbox_inches="tight")
        plt.close(fig)
        print(f"  saved llm_behaviour/{fname}")

    # 4b. Total messages vs max_cycles scatter - all threads in one plot
    if per_run_df is not None:
        THREAD_MARKERS = {
            thread_ids[0]: "o",
            thread_ids[1]: "s",
            thread_ids[2]: "^",
        }

        fig, ax = plt.subplots(figsize=(8, 5.5))
        fig.suptitle("Total messages vs max cycles (per run)", fontsize=FS_SUPTITLE)

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

        # Build legend: variant patches + thread markers
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

        ax.set_xlabel("Max cycles", fontsize=FS_AXLABEL)
        ax.set_ylabel("Total messages", fontsize=FS_AXLABEL)
        ax.tick_params(labelsize=FS_TICK)
        ax.yaxis.grid(True)
        ax.spines[["top", "right"]].set_visible(False)

        fig.tight_layout(rect=[0, 0.1, 1, 1])
        fig.legend(
            handles=variant_patches + thread_handles,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.06),
            ncol=len(variant_patches + thread_handles),
            fontsize=FS_LEGEND,
            framealpha=0.7,
            edgecolor="#aaaaaa",
        )

        fname = "all_scatter_messages_vs_cycles.pdf"
        fig.savefig(llm_dir / fname, format="pdf", bbox_inches="tight")
        plt.close(fig)
        print(f"  saved llm_behaviour/{fname}")

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
    parser.add_argument("--out_dir",    default="convai/plots")
    args = parser.parse_args()

    summary_df    = load_summary(Path(args.summary))
    pv_df         = load_pv_baseline(Path(args.pv_bl))
    pv_pooled_df  = load_pv_pooled(Path(args.pv_pooled))
    per_run_df    = load_per_run(Path(args.per_run))
    out_dir       = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if pv_pooled_df is not None:
        print(f"Pooled p-values loaded: {len(pv_pooled_df)} rows from '{args.pv_pooled}'")
    else:
        print(f"WARNING: pooled p-value file not found at '{args.pv_pooled}'. "
              "Falling back to per-thread file for significance stars.")

    thread_ids = get_thread_ids(summary_df)
    print(f"Threads found: {thread_ids}")

    # Build and merge "all threads" aggregate rows
    all_rows = build_all_rows(summary_df, thread_ids)
    combined_df = pd.concat([summary_df, all_rows], ignore_index=True)

    print("\n-- Transition Δ% plots --")
    make_transition_plots(combined_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df)

    print("\n-- Outcome plots --")
    make_outcome_plots(combined_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df)

    print("\n-- LLM behaviour plots --")
    make_llm_behaviour_plots(combined_df, pv_df, pv_pooled_df, out_dir, thread_ids, per_run_df)

    print(f"\nDone. All plots saved under '{out_dir}/'")
    print("\nOutput structure:")
    print("  transitions/  - Δ% for each of the 4 key transitions, per thread + all")
    print("  outcomes/     - % infected/vaccinated/effectiveness, absolute + delta")
    print("  heatmap/      - Δ% heatmap: 4 transitions × 6 cases")
    print("  llm_behaviour/- msgs/cycle bar charts + total messages vs max_cycles scatter")


if __name__ == "__main__":
    main()