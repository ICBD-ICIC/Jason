"""
plot_simulations.py

Generates bar-chart PDFs comparing simulation configs per thread and metric.

Reads three CSVs produced by analyze_simulations.py:
  --summary   simulation_results.csv
  --pv_bl     simulation_results_pvalues_variant_vs_baseline.csv

For every (metric, thread_id) pair it produces two PDFs:
  <out_dir>/<metric>/<thread_id>_cautious.pdf
  <out_dir>/<metric>/<thread_id>_credulous.pdf

Each PDF contains ONE figure with:
  - x-axis:  baseline, 25pct, 50pct, 75pct  (4 config groups)
  - bars:    side-by-side 600 (blue) and 600_llm (orange), with std error bars
  - p-value annotations:
      * between the two bars in each group  (600 vs 600_llm)
      * above each non-baseline group comparing it to baseline
        (one bracket per variant: 600 and 600_llm)

Usage:
  python plot_simulations.py \\
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
COLOUR = {600: "#4C72B0", "600_llm": "#DD8452"}
VARIANT_LABEL = {600: "600", "600_llm": "600-LLM"}

# ── significance thresholds ───────────────────────────────────────────────────
STAR_THRESHOLDS = [(0.001, "***"), (0.01, "**"), (0.05, "*"), (1.0, "ns")]


def stars(p: float | None) -> str:
    if p is None:
        return ""
    for threshold, label in STAR_THRESHOLDS:
        if p < threshold:
            return label
    return "ns"


# ── annotation helpers ────────────────────────────────────────────────────────

def annotate_bracket(ax, x1: float, x2: float, y: float, h: float, label: str,
                     fontsize: int = 7, color: str = "black") -> None:
    """Draw a bracket from x1 to x2 at height y with a significance label."""
    if not label or label == "ns":
        return
    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], lw=0.8, c=color)
    ax.text((x1 + x2) / 2, y + h, label,
            ha="center", va="bottom", fontsize=fontsize, color=color)


def annotate_pair(ax, x_center: float, y_top: float, h: float, label: str,
                  fontsize: int = 7) -> None:
    """Draw a vertical bracket above a pair of bars (600 vs 600_llm)."""
    if not label or label == "ns":
        return
    ax.annotate(
        label,
        xy=(x_center, y_top + h),
        ha="center", va="bottom",
        fontsize=fontsize,
        color="dimgray",
    )


# ── core plotting function ────────────────────────────────────────────────────

def plot_group(
    ax: plt.Axes,
    configs: list[str],          # ordered list: ["baseline","25pct","50pct","75pct"]
    config_labels: list[str],    # human-readable x-tick labels
    means: dict[str, dict[str, float]],   # means[variant][config]
    stds:  dict[str, dict[str, float]],   # stds[variant][config]
    pv_pair: dict[str, float | None],     # pv_pair[config] = p(600 vs llm) for that config
    pv_bl_600: dict[str, float | None],   # pv_bl_600[config] = p(baseline vs config) for 600
    pv_bl_llm: dict[str, float | None],   # pv_bl_llm[config] = p(baseline vs config) for llm
    metric: str,
    title: str,
) -> None:
    """Fill a single Axes with the grouped bar chart + all annotations."""

    n_configs  = len(configs)
    bar_width  = 0.35
    group_gap  = 1.0          # distance between group centres
    x_centres  = np.arange(n_configs) * group_gap

    variants = [600, "600_llm"]

    # ── draw bars ────────────────────────────────────────────────────────────
    bar_objects: dict[str, list] = {}
    for vi, variant in enumerate(variants):
        offset = (vi - 0.5) * bar_width
        xs = x_centres + offset
        ys = [means[variant].get(cfg, 0.0) or 0.0 for cfg in configs]
        es = [stds[variant].get(cfg,  0.0) or 0.0 for cfg in configs]

        bars = ax.bar(
            xs, ys, bar_width,
            yerr=es, capsize=3,
            color=COLOUR[variant], alpha=0.85,
            label=VARIANT_LABEL[variant],
            error_kw={"elinewidth": 0.8, "ecolor": "black"},
        )
        bar_objects[variant] = bars

    # Determine a comfortable annotation ceiling
    all_vals = []
    for variant in variants:
        for cfg in configs:
            m = means[variant].get(cfg) or 0.0
            s = stds[variant].get(cfg)  or 0.0
            all_vals.append(m + s)
    y_ceil = max(all_vals) if all_vals else 1.0
    step   = y_ceil * 0.07   # vertical step between annotation levels

    # ── 600 vs 600_llm annotation (above each group) ─────────────────────────
    for ci, cfg in enumerate(configs):
        p = pv_pair.get(cfg)
        label = stars(p)
        if not label or label == "ns":
            continue
        x_600    = x_centres[ci] - bar_width / 2
        x_llm    = x_centres[ci] + bar_width / 2
        y_pair   = y_ceil + step
        annotate_bracket(ax, x_600, x_llm, y_pair, step * 0.4, label,
                         fontsize=7, color="dimgray")

    # ── baseline vs variant annotation (per variant, skip baseline itself) ────
    baseline_idx = 0
    x_bl_600 = x_centres[baseline_idx] - bar_width / 2
    x_bl_llm = x_centres[baseline_idx] + bar_width / 2

    level_600 = y_ceil + step * 2.5
    level_llm = y_ceil + step * 2.5

    for ci, cfg in enumerate(configs[1:], start=1):   # skip baseline
        # 600 variant
        p600 = pv_bl_600.get(cfg)
        lbl600 = stars(p600)
        if lbl600 and lbl600 != "ns":
            x_var_600 = x_centres[ci] - bar_width / 2
            annotate_bracket(
                ax, x_bl_600, x_var_600,
                level_600, step * 0.4, lbl600,
                fontsize=7, color=COLOUR[600],
            )
            level_600 += step * 1.6

        # 600_llm variant
        p_llm = pv_bl_llm.get(cfg)
        lbl_llm = stars(p_llm)
        if lbl_llm and lbl_llm != "ns":
            x_var_llm = x_centres[ci] + bar_width / 2
            annotate_bracket(
                ax, x_bl_llm, x_var_llm,
                level_llm, step * 0.4, lbl_llm,
                fontsize=7, color=COLOUR["600_llm"],
            )
            level_llm += step * 1.6

    # ── cosmetics ─────────────────────────────────────────────────────────────
    top_y = max(level_600, level_llm) + step * 2
    ax.set_ylim(bottom=0, top=top_y)
    ax.set_xticks(x_centres)
    ax.set_xticklabels(config_labels, fontsize=8)
    ax.set_ylabel(metric, fontsize=8)
    ax.set_title(title, fontsize=9, pad=4)
    ax.yaxis.grid(True, linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


# ── build lookup tables from CSVs ─────────────────────────────────────────────

def load_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # keep only data rows (not the p_value_600_vs_llm rows)
    df = df[df["variant"].isin([600, "600_llm"])].copy()
    return df


def load_pv_600_llm(path: Path) -> pd.DataFrame:
    """Extract 600 vs llm p-values from the summary CSV (variant == p_value_600_vs_llm)."""
    df = pd.read_csv(path)
    df = df[df["variant"] == "p_value_600_vs_llm"].copy()
    return df


def load_pv_baseline(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def get_thread_ids(summary_df: pd.DataFrame) -> list[str]:
    """Return all thread IDs (configs that are pure digit strings)."""
    tcs = summary_df["thread_config"].unique()
    return sorted(tc for tc in tcs if re.fullmatch(r"\d+", tc))


def get_metric_columns(summary_df: pd.DataFrame) -> list[str]:
    """Return metric names from columns ending in '_mean'."""
    return [c[:-5] for c in summary_df.columns if c.endswith("_mean")]


# ── main plotting loop ─────────────────────────────────────────────────────────

CAUTIOUS_SUFFIXES  = ["25pct_cautious",  "50pct_cautious",  "75pct_cautious"]
CREDULOUS_SUFFIXES = ["25pct_credulous", "50pct_credulous", "75pct_credulous"]

CONFIG_LABEL = {
    "baseline":       "Baseline",
    "25pct_cautious":  "25 %",
    "50pct_cautious":  "50 %",
    "75pct_cautious":  "75 %",
    "25pct_credulous": "25 %",
    "50pct_credulous": "50 %",
    "75pct_credulous": "75 %",
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


def make_plots(
    summary_df:    pd.DataFrame,
    pv_600llm_df:  pd.DataFrame,
    pv_baseline_df: pd.DataFrame,
    out_dir:       Path,
) -> None:

    metrics    = get_metric_columns(summary_df)
    thread_ids = get_thread_ids(summary_df)

    total = len(metrics) * len(thread_ids) * 2
    done  = 0

    for metric in metrics:
        mean_col = f"{metric}_mean"
        std_col  = f"{metric}_std"
        if mean_col not in summary_df.columns:
            continue

        metric_dir = out_dir / metric
        metric_dir.mkdir(parents=True, exist_ok=True)

        for thread_id in thread_ids:

            # ── collect means / stds per variant per config ───────────────
            means: dict[str, dict[str, float]] = {600: {}, "600_llm": {}}
            stds:  dict[str, dict[str, float]] = {600: {}, "600_llm": {}}

            for variant in [600, "600_llm"]:
                sub = summary_df[
                    (summary_df["variant"] == variant) &
                    (summary_df["thread_config"].str.startswith(thread_id))
                ]
                for _, row in sub.iterrows():
                    tc  = row["thread_config"]
                    cfg = "baseline" if tc == thread_id else tc[len(thread_id) + 1:]
                    means[variant][cfg] = row.get(mean_col) or 0.0
                    stds[variant][cfg]  = row.get(std_col)  or 0.0

            # ── 600 vs llm p-values ───────────────────────────────────────
            pv_pair: dict[str, float | None] = {}
            sub_pv = pv_600llm_df[
                pv_600llm_df["thread_config"].str.startswith(thread_id)
            ]
            for _, row in sub_pv.iterrows():
                tc  = row["thread_config"]
                cfg = "baseline" if tc == thread_id else tc[len(thread_id) + 1:]
                pv_pair[cfg] = row.get(mean_col)   # p-value stored in _mean col

            # ── baseline vs variant p-values (per variant) ────────────────
            def bl_pv(variant: str) -> dict[str, float | None]:
                sub = pv_baseline_df[
                    (pv_baseline_df["variant"]   == variant) &
                    (pv_baseline_df["thread_id"] == thread_id) &
                    (pv_baseline_df["metric"]    == metric)
                ]
                return dict(zip(sub["config"], sub["p_value"]))

            pv_bl_600 = bl_pv(600)
            pv_bl_llm = bl_pv("600_llm")

            # ── draw cautious PDF ─────────────────────────────────────────
            for group_name, suffixes in [
                ("cautious",  CAUTIOUS_SUFFIXES),
                ("credulous", CREDULOUS_SUFFIXES),
            ]:
                configs       = ["baseline"] + suffixes
                config_labels = [CONFIG_LABEL[c] for c in configs]

                fig, ax = plt.subplots(figsize=(7, 4.5))

                plot_group(
                    ax=ax,
                    configs=configs,
                    config_labels=config_labels,
                    means=means,
                    stds=stds,
                    pv_pair=pv_pair,
                    pv_bl_600=pv_bl_600,
                    pv_bl_llm=pv_bl_llm,
                    metric=METRIC_LABEL.get(metric, metric),
                    title=f"{METRIC_LABEL.get(metric, metric)}  —  thread {thread_id}  ({group_name})",
                )

                # legend
                handles = [
                    mpatches.Patch(color=COLOUR[v], alpha=0.85, label=VARIANT_LABEL[v])
                    for v in [600, "600_llm"]
                ]
                # star legend
                star_lines = [
                    mpatches.Patch(color="none", label="*** p<0.001"),
                    mpatches.Patch(color="none", label="**  p<0.01"),
                    mpatches.Patch(color="none", label="*   p<0.05"),
                ]
                ax.legend(
                    handles=handles + star_lines,
                    fontsize=7, loc="upper right",
                    framealpha=0.6, edgecolor="none",
                )

                fig.tight_layout()
                pdf_path = metric_dir / f"{thread_id}_{group_name}.pdf"
                fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
                plt.close(fig)

                done += 1
                print(f"  [{done}/{total}] saved {pdf_path.relative_to(out_dir)}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Plot convai simulation results.")
    parser.add_argument(
        "--summary",
        type=str,
        default="simulation_results.csv",
        help="Path to simulation_results.csv",
    )
    parser.add_argument(
        "--pv_bl",
        type=str,
        default="simulation_results_pvalues_variant_vs_baseline.csv",
        help="Path to the baseline-vs-variant p-values CSV",
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default="plots",
        help="Output directory for PDFs",
    )
    args = parser.parse_args()

    summary_path = Path(args.summary)
    pv_bl_path   = Path(args.pv_bl)
    out_dir      = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading summary:            {summary_path}")
    print(f"Loading baseline p-values:  {pv_bl_path}")

    summary_df     = load_summary(summary_path)
    pv_600llm_df   = load_pv_600_llm(summary_path)   # from same file, different rows
    pv_baseline_df = load_pv_baseline(pv_bl_path)

    thread_ids = get_thread_ids(summary_df)
    metrics    = get_metric_columns(summary_df)
    print(f"Found {len(thread_ids)} thread(s), {len(metrics)} metric(s).")
    print(f"Generating {len(metrics) * len(thread_ids) * 2} PDFs in '{out_dir}/'...\n")

    make_plots(summary_df, pv_600llm_df, pv_baseline_df, out_dir)

    print(f"\nDone. All PDFs saved under '{out_dir}/'.")
    print("Structure:  <out_dir>/<metric>/<thread_id>_cautious.pdf")
    print("            <out_dir>/<metric>/<thread_id>_credulous.pdf")


if __name__ == "__main__":
    main()