"""
analysis_results_plots.py

Generates bar-chart PDFs comparing simulation configs per thread and metric.

Reads three CSVs produced by analyze_simulations.py:
  --summary   simulation_results.csv
  --pv_bl     simulation_results_pvalues_variant_vs_baseline.csv

For every (metric, thread_id) pair it produces:
  <out_dir>/<metric>/<thread_id>_cautious.pdf         absolute values, cautious variants
  <out_dir>/<metric>/<thread_id>_credulous.pdf        absolute values, credulous variants
  <out_dir>/<metric>/<thread_id>_diff.pdf             Δ vs baseline, all 6 variants, 600 & 600_llm
  <out_dir>/max_cycles/<thread_id>_avg.pdf            max_cycles + avg_cycles side-by-side (if available)

Plus one "all-threads" aggregate for every metric:
  <out_dir>/<metric>/all_cautious.pdf
  <out_dir>/<metric>/all_credulous.pdf
  <out_dir>/<metric>/all_diff.pdf
  <out_dir>/max_cycles/all_avg.pdf

Usage:
  python analysis_results_plots.py \\
      --summary  simulation_results.csv \\
      --pv_bl    simulation_results_pvalues_variant_vs_baseline.csv \\
      --out_dir  plots/
"""

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

# ── colour / style ────────────────────────────────────────────────────────────
COLOUR = {"600": "#4C72B0", "600_llm": "#DD8452"}
VARIANT_LABEL = {"600": "600", "600_llm": "600-LLM"}

CAUTIOUS_SUFFIXES  = ["25pct_cautious",  "50pct_cautious",  "75pct_cautious"]
CREDULOUS_SUFFIXES = ["25pct_credulous", "50pct_credulous", "75pct_credulous"]
ALL_SUFFIXES       = CAUTIOUS_SUFFIXES + CREDULOUS_SUFFIXES

DIFF_LABELS = {
    "25pct_cautious":  "25% Caut",
    "50pct_cautious":  "50% Caut",
    "75pct_cautious":  "75% Caut",
    "25pct_credulous": "25% Cred",
    "50pct_credulous": "50% Cred",
    "75pct_credulous": "75% Cred",
}

CONFIG_LABEL = {
    "baseline":         "Baseline",
    "25pct_cautious":   "25 %",
    "50pct_cautious":   "50 %",
    "75pct_cautious":   "75 %",
    "25pct_credulous":  "25 %",
    "50pct_credulous":  "50 %",
    "75pct_credulous":  "75 %",
}

METRIC_LABEL = {
    "pct_infected":              "Infected agents (%)",
    "pct_vaccinated":            "Vaccinated agents (%)",
    "pct_neutral":               "Neutral agents (%)",
    "vax_effectiveness":         "Vaccination effectiveness (%)",
    "max_cycles":                "Max cycles",
    "total_messages":            "Total messages",
    "pct_msg_vaccinated":        "Messages from vaccinated (%)",
    "pct_msg_infected":          "Messages from infected (%)",
    "pct_agents_changed":        "Agents that changed state (%)",
    "avg_transitions_per_agent": "Avg transitions / agent",
}

# Metrics where a "difference vs baseline" makes physical sense
# Colours for the 6 transition types in stacked bars
TRANS_KEYS = [
    "trans_neutral_to_infected",
    "trans_neutral_to_vaccinated",
    "trans_infected_to_neutral",
    "trans_infected_to_vaccinated",
    "trans_vaccinated_to_neutral",
    "trans_vaccinated_to_infected",
]
TRANS_COLOURS = {
    "trans_neutral_to_infected":    "#E15759",
    "trans_neutral_to_vaccinated":  "#4E79A7",
    "trans_infected_to_neutral":    "#F28E2B",
    "trans_infected_to_vaccinated": "#76B7B2",
    "trans_vaccinated_to_neutral":  "#B07AA1",
    "trans_vaccinated_to_infected": "#FF9DA7",
}
TRANS_LABELS = {
    "trans_neutral_to_infected":    "Neutral → Infected",
    "trans_neutral_to_vaccinated":  "Neutral → Vaccinated",
    "trans_infected_to_neutral":    "Infected → Neutral",
    "trans_infected_to_vaccinated": "Infected → Vaccinated",
    "trans_vaccinated_to_neutral":  "Vaccinated → Neutral",
    "trans_vaccinated_to_infected": "Vaccinated → Infected",
}

DIFF_ELIGIBLE_METRICS = {
    "pct_infected", "pct_vaccinated", "pct_neutral",
    "vax_effectiveness",
    "max_cycles",
    "total_messages",
    "pct_msg_vaccinated", "pct_msg_infected",
    "pct_agents_changed", "avg_transitions_per_agent",
}

# ── significance thresholds ───────────────────────────────────────────────────
STAR_THRESHOLDS = [(0.001, "***"), (0.01, "**"), (0.05, "*"), (1.0, "ns")]


def stars(p) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    for threshold, label in STAR_THRESHOLDS:
        if p < threshold:
            return label
    return "ns"


# ── annotation helpers ────────────────────────────────────────────────────────

def annotate_bracket(ax, x1, x2, y, h, label, fontsize=7, color="black"):
    if not label or label == "ns":
        return
    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], lw=0.8, c=color)
    ax.text((x1 + x2) / 2, y + h, label,
            ha="center", va="bottom", fontsize=fontsize, color=color)


# ── absolute-value grouped bar chart ─────────────────────────────────────────

def plot_group(
    ax,
    configs, config_labels,
    means, stds,
    pv_pair, pv_bl_600, pv_bl_llm,
    metric, title,
):
    """Side-by-side bars (600 / 600_llm) with significance brackets."""
    variants  = ["600", "600_llm"]
    bar_width = 0.35
    x_centres = np.arange(len(configs)) * 1.0

    for vi, variant in enumerate(variants):
        offset = (vi - 0.5) * bar_width
        xs = x_centres + offset
        ys = [means[variant].get(cfg, 0.0) or 0.0 for cfg in configs]
        es = [stds[variant].get(cfg,  0.0) or 0.0 for cfg in configs]
        ax.bar(xs, ys, bar_width, yerr=es, capsize=3,
               color=COLOUR[variant], alpha=0.85,
               label=VARIANT_LABEL[variant],
               error_kw={"elinewidth": 0.8, "ecolor": "black"})

    all_vals = [
        (means[v].get(c) or 0.0) + (stds[v].get(c) or 0.0)
        for v in variants for c in configs
    ]
    y_ceil = max(all_vals) if all_vals else 1.0
    step   = max(y_ceil * 0.07, 0.5)

    for ci, cfg in enumerate(configs):
        p = pv_pair.get(cfg)
        lbl = stars(p)
        if lbl and lbl != "ns":
            x0 = x_centres[ci] - bar_width / 2
            x1 = x_centres[ci] + bar_width / 2
            annotate_bracket(ax, x0, x1, y_ceil + step, step * 0.4, lbl,
                             fontsize=7, color="dimgray")

    x_bl_600 = x_centres[0] - bar_width / 2
    x_bl_llm = x_centres[0] + bar_width / 2
    level_600 = level_llm = y_ceil + step * 2.5

    for ci, cfg in enumerate(configs[1:], start=1):
        p600 = pv_bl_600.get(cfg); lbl600 = stars(p600)
        if lbl600 and lbl600 != "ns":
            annotate_bracket(ax, x_bl_600, x_centres[ci] - bar_width / 2,
                             level_600, step * 0.4, lbl600,
                             fontsize=7, color=COLOUR["600"])
            level_600 += step * 1.6

        pllm = pv_bl_llm.get(cfg); lblllm = stars(pllm)
        if lblllm and lblllm != "ns":
            annotate_bracket(ax, x_bl_llm, x_centres[ci] + bar_width / 2,
                             level_llm, step * 0.4, lblllm,
                             fontsize=7, color=COLOUR["600_llm"])
            level_llm += step * 1.6

    top_y = max(level_600, level_llm) + step * 2
    ax.set_ylim(bottom=0, top=top_y)
    ax.set_xticks(x_centres)
    ax.set_xticklabels(config_labels, fontsize=8)
    ax.set_ylabel(metric, fontsize=8)
    ax.set_title(title, fontsize=9, pad=4)
    ax.yaxis.grid(True, linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


# ── DIFFERENCE plot ───────────────────────────────────────────────────────────

def plot_diff(
    ax,
    suffixes,           # all 6 non-baseline suffixes, in order
    means, stds,        # means[variant][cfg], stds[variant][cfg]
    pv_bl_600, pv_bl_llm,
    metric, title,
):
    """
    Bar chart of (variant_mean - baseline_mean) for every suffix,
    side-by-side for 600 and 600_llm.
    Baseline is the implicit zero line.
    Error bars propagate both stds in quadrature.
    Significance brackets compare each variant to baseline (coloured by variant).
    """
    variants  = ["600", "600_llm"]
    bar_width = 0.35
    n         = len(suffixes)
    x_centres = np.arange(n) * 1.0

    diffs = {v: [] for v in variants}
    errs  = {v: [] for v in variants}
    for suf in suffixes:
        for v in variants:
            bm  = means[v].get("baseline", 0.0) or 0.0
            vm  = means[v].get(suf,        0.0) or 0.0
            bs  = stds[v].get("baseline",  0.0) or 0.0
            vs_ = stds[v].get(suf,         0.0) or 0.0
            diffs[v].append(vm - bm)
            errs[v].append(np.sqrt(bs**2 + vs_**2))

    for vi, v in enumerate(variants):
        offset = (vi - 0.5) * bar_width
        xs = x_centres + offset
        ys = diffs[v]
        es = errs[v]
        ax.bar(xs, ys, bar_width, yerr=es, capsize=3,
               color=COLOUR[v], alpha=0.85,
               label=VARIANT_LABEL[v],
               error_kw={"elinewidth": 0.8, "ecolor": "black"})

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.6)

    # annotation ceiling/floor
    all_with_err = []
    for v in variants:
        for d, e in zip(diffs[v], errs[v]):
            all_with_err.append(d + e)
            all_with_err.append(d - e)
    y_top  = max(all_with_err) if all_with_err else 1.0
    y_bot  = min(all_with_err) if all_with_err else -1.0
    span   = max(abs(y_top), abs(y_bot))
    step   = max(span * 0.07, 0.5)
    ceil   = y_top + step

    for ci, suf in enumerate(suffixes):
        p600 = pv_bl_600.get(suf); lbl600 = stars(p600)
        if lbl600 and lbl600 != "ns":
            x0 = x_centres[ci] - bar_width / 2
            annotate_bracket(ax, x0, x0, ceil, step * 0.4, lbl600,
                             fontsize=7, color=COLOUR["600"])

        pllm = pv_bl_llm.get(suf); lblllm = stars(pllm)
        if lblllm and lblllm != "ns":
            x1 = x_centres[ci] + bar_width / 2
            annotate_bracket(ax, x1, x1, ceil + step * 0.6, step * 0.4, lblllm,
                             fontsize=7, color=COLOUR["600_llm"])

    ax.set_xticks(x_centres)
    ax.set_xticklabels([DIFF_LABELS[s] for s in suffixes], fontsize=7, rotation=15, ha="right")
    ax.set_ylabel(f"Δ {metric} vs Baseline", fontsize=8)
    ax.set_title(title, fontsize=9, pad=4)
    ax.yaxis.grid(True, linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


# ── max_cycles: absolute + avg side-by-side ───────────────────────────────────

def plot_max_and_avg_cycles(
    ax_max, ax_avg,
    configs, config_labels,
    means_max, stds_max,
    means_avg, stds_avg,
    pv_pair_max, pv_bl_600_max, pv_bl_llm_max,
    pv_pair_avg, pv_bl_600_avg, pv_bl_llm_avg,
    group_name, thread_label,
):
    """Fill two axes: left = max_cycles, right = avg_cycles (if available)."""
    plot_group(ax_max, configs, config_labels,
               means_max, stds_max,
               pv_pair_max, pv_bl_600_max, pv_bl_llm_max,
               METRIC_LABEL["max_cycles"],
               f"Max cycles - {thread_label} ({group_name})")

    # avg_cycles might not exist if the column wasn't computed
    has_avg = any(
        means_avg[v].get(c) is not None
        for v in ["600", "600_llm"] for c in configs
    )
    if has_avg:
        plot_group(ax_avg, configs, config_labels,
                   means_avg, stds_avg,
                   pv_pair_avg, pv_bl_600_avg, pv_bl_llm_avg,
                   "Avg cycles",
                   f"Avg cycles - {thread_label} ({group_name})")
    else:
        ax_avg.set_visible(False)


# ── CSV loading ───────────────────────────────────────────────────────────────

def load_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["variant"].isin(["600", "600_llm"])].copy()
    df["variant"] = df["variant"].astype(str)
    return df


def load_pv_600_llm(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["variant"] == "p_value_600_vs_llm"].copy()
    return df


def load_pv_baseline(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["variant"] = df["variant"].astype(str)
    return df


def get_thread_ids(summary_df: pd.DataFrame) -> list:
    tcs = summary_df["thread_config"].unique()
    return sorted(tc for tc in tcs if re.fullmatch(r"\d+", str(tc)))


def get_metric_columns(summary_df: pd.DataFrame) -> list:
    return [c[:-5] for c in summary_df.columns if c.endswith("_mean")]


# ── data extraction helpers ───────────────────────────────────────────────────

def extract_means_stds(summary_df, thread_id):
    """
    Returns means[variant][cfg], stds[variant][cfg] for all configs
    whose thread_config starts with thread_id.
    """
    means = {"600": {}, "600_llm": {}}
    stds  = {"600": {}, "600_llm": {}}
    for variant in ["600", "600_llm"]:
        sub = summary_df[
            (summary_df["variant"] == variant) &
            (summary_df["thread_config"].astype(str).str.startswith(str(thread_id)))
        ]
        for _, row in sub.iterrows():
            tc  = str(row["thread_config"])
            cfg = "baseline" if tc == str(thread_id) else tc[len(str(thread_id)) + 1:]
            for col in summary_df.columns:
                if col.endswith("_mean"):
                    metric = col[:-5]
                    means[variant].setdefault(metric, {})[cfg] = row.get(col)
                elif col.endswith("_std"):
                    metric = col[:-4]
                    stds[variant].setdefault(metric, {})[cfg] = row.get(col)
    return means, stds


def extract_pv_pair(pv_600llm_df, thread_id, metric):
    mean_col = f"{metric}_mean"
    sub = pv_600llm_df[
        pv_600llm_df["thread_config"].astype(str).str.startswith(str(thread_id))
    ]
    result = {}
    for _, row in sub.iterrows():
        tc  = str(row["thread_config"])
        cfg = "baseline" if tc == str(thread_id) else tc[len(str(thread_id)) + 1:]
        result[cfg] = row.get(mean_col)
    return result


def extract_pv_bl(pv_baseline_df, variant, thread_id, metric):
    sub = pv_baseline_df[
        (pv_baseline_df["variant"]   == variant) &
        (pv_baseline_df["thread_id"].astype(str) == str(thread_id)) &
        (pv_baseline_df["metric"]    == metric)
    ]
    return dict(zip(sub["config"].astype(str), sub["p_value"]))


# ── aggregate across threads ("all") ─────────────────────────────────────────

def build_all_threads_data(summary_df: pd.DataFrame, thread_ids: list) -> pd.DataFrame:
    """
    Return a synthetic summary_df where thread_config is replaced by
    'all' / 'all_<suffix>' rows whose means are the across-thread averages
    and whose stds are the across-thread standard deviations of per-thread means.
    """
    metric_cols = [c for c in summary_df.columns
                   if c.endswith("_mean") or c.endswith("_std")]
    rows = []
    for variant in ["600", "600_llm"]:
        sub = summary_df[summary_df["variant"] == variant].copy()
        # collect all unique configs (raw thread_config values)
        all_tcs = sub["thread_config"].astype(str).unique()

        # map each thread_config to its canonical suffix
        suffix_map: dict[str, str] = {}
        for tc in all_tcs:
            for tid in map(str, thread_ids):
                if tc == tid:
                    suffix_map[tc] = "baseline"; break
                elif tc.startswith(tid + "_"):
                    suffix_map[tc] = tc[len(tid) + 1:]; break

        sub = sub[sub["thread_config"].astype(str).isin(suffix_map)].copy()
        sub["_suffix"] = sub["thread_config"].astype(str).map(suffix_map)

        for suffix, grp in sub.groupby("_suffix"):
            tc_label = "all" if suffix == "baseline" else f"all_{suffix}"
            row: dict = {"variant": variant, "thread_config": tc_label}
            for col in metric_cols:
                if col.endswith("_mean"):
                    vals = grp[col].dropna().values
                    row[col] = float(np.mean(vals)) if len(vals) else None
                    row[col.replace("_mean", "_std")] = (
                        float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
                    )
            rows.append(row)

    return pd.DataFrame(rows)


# ── standard figure for absolute-value grouped bars ──────────────────────────

def _std_fig_abs(thread_id, metric, group_name,
                 summary_df, pv_600llm_df, pv_baseline_df):
    """Return (fig, ax) with a grouped bar chart for one thread+metric+group."""
    suffixes = CAUTIOUS_SUFFIXES if group_name == "cautious" else CREDULOUS_SUFFIXES
    configs  = ["baseline"] + suffixes
    config_labels = [CONFIG_LABEL[c] for c in configs]

    means_all, stds_all = extract_means_stds(summary_df, thread_id)
    means = {v: means_all[v].get(metric, {}) for v in ["600", "600_llm"]}
    stds  = {v: stds_all[v].get(metric, {})  for v in ["600", "600_llm"]}

    pv_pair   = extract_pv_pair(pv_600llm_df, thread_id, metric)
    pv_bl_600 = extract_pv_bl(pv_baseline_df, "600",     thread_id, metric)
    pv_bl_llm = extract_pv_bl(pv_baseline_df, "600_llm", thread_id, metric)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    plot_group(ax, configs, config_labels,
               means, stds, pv_pair, pv_bl_600, pv_bl_llm,
               METRIC_LABEL.get(metric, metric),
               f"{METRIC_LABEL.get(metric, metric)}  -  thread {thread_id}  ({group_name})")
    _add_legend(ax)
    fig.tight_layout()
    return fig


def _std_fig_diff(thread_id, metric,
                  summary_df, pv_baseline_df):
    """Return (fig, ax) with a difference-vs-baseline chart for one thread+metric."""
    means_all, stds_all = extract_means_stds(summary_df, thread_id)
    means = {v: means_all[v].get(metric, {}) for v in ["600", "600_llm"]}
    stds  = {v: stds_all[v].get(metric, {})  for v in ["600", "600_llm"]}

    pv_bl_600 = extract_pv_bl(pv_baseline_df, "600",     thread_id, metric)
    pv_bl_llm = extract_pv_bl(pv_baseline_df, "600_llm", thread_id, metric)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot_diff(ax, ALL_SUFFIXES, means, stds,
              pv_bl_600, pv_bl_llm,
              METRIC_LABEL.get(metric, metric),
              f"Δ vs Baseline - {METRIC_LABEL.get(metric, metric)} - thread {thread_id}")
    _add_legend(ax)
    fig.tight_layout()
    return fig


def _add_legend(ax):
    handles = [
        mpatches.Patch(color=COLOUR[v], alpha=0.85, label=VARIANT_LABEL[v])
        for v in ["600", "600_llm"]
    ]
    star_lines = [
        mpatches.Patch(color="none", label="*** p<0.001"),
        mpatches.Patch(color="none", label="**  p<0.01"),
        mpatches.Patch(color="none", label="*   p<0.05"),
    ]
    ax.legend(handles=handles + star_lines,
              fontsize=7, loc="upper right",
              framealpha=0.6, edgecolor="none")


# ── max_cycles special figure (max + avg, side-by-side) ──────────────────────

def _max_cycles_fig(thread_id, group_name,
                    summary_df, pv_600llm_df, pv_baseline_df):
    """Two side-by-side panels: max_cycles and avg_cycles (if present)."""
    suffixes = CAUTIOUS_SUFFIXES if group_name == "cautious" else CREDULOUS_SUFFIXES
    configs  = ["baseline"] + suffixes
    config_labels = [CONFIG_LABEL[c] for c in configs]

    means_all, stds_all = extract_means_stds(summary_df, thread_id)

    def _ms(metric):
        return (
            {v: means_all[v].get(metric, {}) for v in ["600", "600_llm"]},
            {v: stds_all[v].get(metric, {})  for v in ["600", "600_llm"]},
        )

    means_max, stds_max = _ms("max_cycles")
    means_avg, stds_avg = _ms("avg_cycles")   # may be empty dicts

    pv_pair_max   = extract_pv_pair(pv_600llm_df, thread_id, "max_cycles")
    pv_bl_600_max = extract_pv_bl(pv_baseline_df, "600",     thread_id, "max_cycles")
    pv_bl_llm_max = extract_pv_bl(pv_baseline_df, "600_llm", thread_id, "max_cycles")
    pv_pair_avg   = extract_pv_pair(pv_600llm_df, thread_id, "avg_cycles")
    pv_bl_600_avg = extract_pv_bl(pv_baseline_df, "600",     thread_id, "avg_cycles")
    pv_bl_llm_avg = extract_pv_bl(pv_baseline_df, "600_llm", thread_id, "avg_cycles")

    has_avg = any(
        means_avg[v].get(c) is not None
        for v in ["600", "600_llm"] for c in configs
    )

    if has_avg:
        fig, (ax_max, ax_avg) = plt.subplots(1, 2, figsize=(14, 4.5))
    else:
        fig, ax_max = plt.subplots(figsize=(7, 4.5))
        ax_avg = None

    plot_group(ax_max, configs, config_labels,
               means_max, stds_max,
               pv_pair_max, pv_bl_600_max, pv_bl_llm_max,
               METRIC_LABEL["max_cycles"],
               f"Max cycles - thread {thread_id} ({group_name})")

    if has_avg and ax_avg is not None:
        plot_group(ax_avg, configs, config_labels,
                   means_avg, stds_avg,
                   pv_pair_avg, pv_bl_600_avg, pv_bl_llm_avg,
                   "Avg cycles",
                   f"Avg cycles - thread {thread_id} ({group_name})")

    _add_legend(ax_max)
    fig.tight_layout()
    return fig


# ── main ──────────────────────────────────────────────────────────────────────

def plot_transitions_stacked(ax, configs, config_labels, means, title):
    """
    100% stacked bar chart of all transition types.
    For each config, two bars side-by-side: 600 (left) and 600_llm (right).
    Each bar is subdivided into the 6 transition types, always summing to 100%.
    """
    variants  = ["600", "600_llm"]
    bar_width = 0.35
    x_centres = np.arange(len(configs)) * 1.0

    for vi, variant in enumerate(variants):
        offset = (vi - 0.5) * bar_width
        xs = x_centres + offset

        bottoms = np.zeros(len(configs))
        for tkey in TRANS_KEYS:
            vals = np.array([
                means[variant].get(tkey, {}).get(cfg, 0.0) or 0.0
                for cfg in configs
            ])
            ax.bar(xs, vals, bar_width,
                   bottom=bottoms,
                   color=TRANS_COLOURS[tkey],
                   label=TRANS_LABELS[tkey] if vi == 0 else "_nolegend_",
                   alpha=0.88)
            bottoms += vals

    ax.set_ylim(0, 105)
    ax.set_xticks(x_centres)
    ax.set_xticklabels(config_labels, fontsize=8)
    # secondary x labels: 600 / 600_llm under each pair
    for ci, xc in enumerate(x_centres):
        ax.text(xc - bar_width / 2, -7, "600",     ha="center", va="top",
                fontsize=6, color=COLOUR["600"])
        ax.text(xc + bar_width / 2, -7, "LLM",     ha="center", va="top",
                fontsize=6, color=COLOUR["600_llm"])
    ax.set_ylabel("% of all transitions", fontsize=8)
    ax.set_title(title, fontsize=9, pad=4)
    ax.yaxis.grid(True, linewidth=0.4, alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=6, loc="upper right", framealpha=0.6,
              edgecolor="none", ncol=2)


def _transitions_fig(thread_id, summary_df):
    """One figure: all configs (baseline + all 6 suffixes) as 100% stacked bars."""
    configs       = ["baseline"] + ALL_SUFFIXES
    trans_config_labels = {
        "baseline":         "Baseline",
        "25pct_cautious":   "25% Caut",
        "50pct_cautious":   "50% Caut",
        "75pct_cautious":   "75% Caut",
        "25pct_credulous":  "25% Cred",
        "50pct_credulous":  "50% Cred",
        "75pct_credulous":  "75% Cred",
    }
    config_labels = [trans_config_labels.get(c, c) for c in configs]

    # collect means for every transition metric
    means_all, _ = extract_means_stds(summary_df, thread_id)

    # build means[variant][trans_key][cfg]
    means = {"600": {}, "600_llm": {}}
    for v in ["600", "600_llm"]:
        for tkey in TRANS_KEYS:
            means[v][tkey] = means_all[v].get(tkey, {})

    fig, ax = plt.subplots(figsize=(10, 5))
    plot_transitions_stacked(
        ax, configs, config_labels, means,
        f"State transitions (% of all) - thread {thread_id}",
    )
    fig.tight_layout()
    return fig


def make_plots(summary_df, pv_600llm_df, pv_baseline_df, out_dir: Path):
    metrics    = get_metric_columns(summary_df)
    thread_ids = get_thread_ids(summary_df)

    # Build the "all-threads" aggregate rows and merge into a combined df
    all_df = build_all_threads_data(summary_df, thread_ids)
    # For "all" we use thread_id token "all" (matches 'all' prefix)
    all_thread_id = "all"
    combined_df = pd.concat([summary_df, all_df], ignore_index=True)

    # We won't have real p-values for "all" (different thread counts),
    # but we still create empty frames so the helpers don't crash.
    empty_pv_bl = pd.DataFrame(columns=pv_baseline_df.columns)
    empty_pv_pair = pd.DataFrame(columns=pv_600llm_df.columns)

    work_items = []

    for thread_id in thread_ids:
        work_items.append(("thread", thread_id))
    work_items.append(("all", all_thread_id))

    total_done = 0

    for wtype, thread_id in work_items:
        # choose the right dataframe
        if wtype == "all":
            s_df     = combined_df  # all_df rows have 'all' / 'all_<suffix>' configs
            pv_pair_df = empty_pv_pair
            pv_bl_df   = empty_pv_bl
            label      = "all threads"
        else:
            s_df     = summary_df
            pv_pair_df = pv_600llm_df
            pv_bl_df   = pv_baseline_df
            label      = str(thread_id)

        for metric in metrics:
            metric_dir = out_dir / metric
            metric_dir.mkdir(parents=True, exist_ok=True)

            # ── absolute cautious / credulous ────────────────────────────
            for group_name in ["cautious", "credulous"]:
                try:
                    fig = _std_fig_abs(thread_id, metric, group_name,
                                       s_df, pv_pair_df, pv_bl_df)
                    # update title to reflect "all"
                    if wtype == "all":
                        for ax in fig.axes:
                            t = ax.get_title()
                            ax.set_title(t.replace(f"thread {thread_id}", "all threads"))
                    fname = f"{thread_id}_{group_name}.pdf"
                    fig.savefig(metric_dir / fname, format="pdf", bbox_inches="tight")
                    plt.close(fig)
                    total_done += 1
                    print(f"  saved {metric}/{fname}")
                except Exception as e:
                    print(f"  [WARN] {metric}/{thread_id}_{group_name}: {e}")

            # ── difference vs baseline ───────────────────────────────────
            if metric in DIFF_ELIGIBLE_METRICS:
                try:
                    fig = _std_fig_diff(thread_id, metric, s_df, pv_bl_df)
                    if wtype == "all":
                        for ax in fig.axes:
                            t = ax.get_title()
                            ax.set_title(t.replace(f"thread {thread_id}", "all threads"))
                    fname = f"{thread_id}_diff.pdf"
                    fig.savefig(metric_dir / fname, format="pdf", bbox_inches="tight")
                    plt.close(fig)
                    total_done += 1
                    print(f"  saved {metric}/{fname}")
                except Exception as e:
                    print(f"  [WARN] {metric}/{thread_id}_diff: {e}")

        # ── max_cycles special: max + avg side-by-side ───────────────────
        if "max_cycles" in metrics:
            mc_dir = out_dir / "max_cycles"
            mc_dir.mkdir(parents=True, exist_ok=True)
            for group_name in ["cautious", "credulous"]:
                try:
                    fig = _max_cycles_fig(thread_id, group_name,
                                          s_df, pv_pair_df, pv_bl_df)
                    if wtype == "all":
                        for ax in fig.axes:
                            t = ax.get_title()
                            ax.set_title(t.replace(f"thread {thread_id}", "all threads"))
                    fname = f"{thread_id}_{group_name}_with_avg.pdf"
                    fig.savefig(mc_dir / fname, format="pdf", bbox_inches="tight")
                    plt.close(fig)
                    total_done += 1
                    print(f"  saved max_cycles/{fname}")
                except Exception as e:
                    print(f"  [WARN] max_cycles/{thread_id}_{group_name}_with_avg: {e}")

        # ── transitions stacked 100% bar ────────────────────────────────
        try:
            trans_dir = out_dir / "transitions"
            trans_dir.mkdir(parents=True, exist_ok=True)
            fig = _transitions_fig(thread_id, s_df)
            if wtype == "all":
                for ax in fig.axes:
                    ax.set_title(ax.get_title().replace(
                        f"thread {thread_id}", "all threads"))
            fname = f"{thread_id}_transitions.pdf"
            fig.savefig(trans_dir / fname, format="pdf", bbox_inches="tight")
            plt.close(fig)
            total_done += 1
            print(f"  saved transitions/{fname}")
        except Exception as e:
            print(f"  [WARN] transitions/{thread_id}: {e}")

    print(f"\nDone. {total_done} PDFs saved under '{out_dir}/'.")


def main():
    parser = argparse.ArgumentParser(description="Plot convai simulation results.")
    parser.add_argument("--summary",  type=str, default="convai/results.csv")
    parser.add_argument("--pv_bl",    type=str,
                        default="convai/results_pvalues_variant_vs_baseline.csv")
    parser.add_argument("--out_dir",  type=str, default="convai/plots")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    pv_bl_path   = Path(args.pv_bl)
    out_dir      = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading summary:            {summary_path}")
    print(f"Loading baseline p-values:  {pv_bl_path}")

    summary_df     = load_summary(summary_path)
    pv_600llm_df   = load_pv_600_llm(summary_path)
    pv_baseline_df = load_pv_baseline(pv_bl_path)

    thread_ids = get_thread_ids(summary_df)
    metrics    = get_metric_columns(summary_df)
    print(f"Found {len(thread_ids)} thread(s), {len(metrics)} metric(s).")

    make_plots(summary_df, pv_600llm_df, pv_baseline_df, out_dir)

    print(f"\nOutput structure:")
    print(f"  <out_dir>/<metric>/<thread_id>_cautious.pdf       absolute values")
    print(f"  <out_dir>/<metric>/<thread_id>_credulous.pdf      absolute values")
    print(f"  <out_dir>/<metric>/<thread_id>_diff.pdf           Δ vs baseline, all 6 variants")
    print(f"  <out_dir>/max_cycles/<thread_id>_*_with_avg.pdf   max + avg cycles")
    print(f"  (same files with 'all' prefix = cross-thread averages)")


if __name__ == "__main__":
    main()