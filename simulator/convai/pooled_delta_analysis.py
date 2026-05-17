"""
pooled_delta_analysis.py

Reads results_per_run.csv produced by analyze_simulations.py, computes a
pooled delta analysis (Wilcoxon signed-rank test across all threads), and writes:

  convai/results_pooled_delta.csv          raw results table
  convai/plots/pooled_delta_heatmap.pdf    significance heatmap

Usage:
  python pooled_delta_analysis.py
  python pooled_delta_analysis.py --per_run convai/results_per_run.csv \
      --csv_out convai/results_pooled_delta.csv \
      --plot_out convai/plots/pooled_delta_heatmap.pdf
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KEY_METRICS = [
    ("pct_infected_susc",          "% infected (susceptibles)"),
    ("pct_vaccinated_susc",        "% vaccinated (susceptibles)"),
    ("vax_effectiveness_susc",     "Vaccination effectiveness"),
    ("trans_neutral_to_infected",  "Trans: neutral → infected (%)"),
    ("trans_neutral_to_vaccinated","Trans: neutral → vaccinated (%)"),
    ("trans_infected_to_vaccinated","Trans: infected → vaccinated (%)"),
    ("trans_vaccinated_to_infected","Trans: vaccinated → infected (%)"),
]

CONFIGS_ORDER = [
    "25pct_cautious", "25pct_credulous",
    "50pct_cautious", "50pct_credulous",
    "75pct_cautious", "75pct_credulous",
]

VARIANTS = ["600", "600_llm"]
VARIANT_LABELS = {"600": "600 (rule-based)", "600_llm": "600_llm (LLM agents)"}

SIG_COLORS = {
    "p<0.01": "#1D9E75",
    "p<0.05": "#5DCAA5",
    "p<0.10": "#9FE1CB",
    "ns":     "#E8E8E4",
}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def compute_deltas(per_run: pd.DataFrame) -> pd.DataFrame:
    per_run = per_run.copy()
    per_run["thread_id"] = per_run["thread_config"].str.extract(r"^(\d+)")
    per_run["suffix"]    = per_run["thread_config"].str.extract(r"^\d+_(.*)")
    per_run["suffix"]    = per_run["suffix"].fillna("baseline")

    metrics   = [m for m, _ in KEY_METRICS]
    baselines = (
        per_run[per_run["suffix"] == "baseline"]
        .groupby(["variant", "thread_id"])[metrics]
        .mean()
    )

    rows = []
    for _, row in per_run[per_run["suffix"] != "baseline"].iterrows():
        key = (row["variant"], row["thread_id"])
        if key not in baselines.index:
            continue
        base = baselines.loc[key]
        r = {
            "variant":   row["variant"],
            "thread_id": row["thread_id"],
            "config":    row["suffix"],
            "run":       row["run"],
        }
        for m in metrics:
            r[f"delta_{m}"] = row[m] - base[m]
        rows.append(r)

    return pd.DataFrame(rows)


def _sig_label(p) -> str:
    if p is None: return "ns"
    if p < 0.01:  return "p<0.01"
    if p < 0.05:  return "p<0.05"
    if p < 0.10:  return "p<0.10"
    return "ns"


def run_wilcoxon(deltas: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for var in VARIANTS:
        for cfg in CONFIGS_ORDER:
            for m, _ in KEY_METRICS:
                col  = f"delta_{m}"
                vals = (
                    deltas[(deltas["variant"] == var) & (deltas["config"] == cfg)][col]
                    .dropna().values
                )
                p = None
                if len(vals) >= 3:
                    try:
                        _, p = stats.wilcoxon(vals, alternative="two-sided")
                    except Exception:
                        pass
                rows.append({
                    "variant":    var,
                    "config":     cfg,
                    "metric":     m,
                    "n":          len(vals),
                    "mean_delta": float(np.mean(vals)) if len(vals) else None,
                    "p_wilcoxon": p,
                    "sig_label":  _sig_label(p),
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# stdout summary
# ---------------------------------------------------------------------------

def print_summary(results: pd.DataFrame) -> None:
    print("\n" + "=" * 72)
    print("POOLED DELTA ANALYSIS  (Wilcoxon signed-rank, n=9 per cell)")
    print("Delta = variant run value minus per-thread baseline mean")
    print("=" * 72)
    for var in VARIANTS:
        print(f"\n--- {VARIANT_LABELS[var]} ---")
        for metric, label in KEY_METRICS:
            print(f"\n  {label}")
            print(f"  {'Config':<22} {'n':>3}  {'Mean delta':>12}  {'p':>8}  Sig")
            print("  " + "-" * 55)
            for cfg in CONFIGS_ORDER:
                r = results[
                    (results["variant"] == var) &
                    (results["config"]  == cfg) &
                    (results["metric"]  == metric)
                ]
                if r.empty:
                    continue
                r = r.iloc[0]
                p_str = f"{r['p_wilcoxon']:.4f}" if r["p_wilcoxon"] is not None else "   n/a"
                d_str = f"{r['mean_delta']:+.2f} pp" if r["mean_delta"] is not None else "   n/a"
                print(f"  {cfg:<22} {r['n']:>3}  {d_str:>12}  {p_str:>8}  {r['sig_label']}")
    print()


# ---------------------------------------------------------------------------
# Heatmap PDF
# ---------------------------------------------------------------------------

def build_heatmap_pdf(results: pd.DataFrame, out_path: Path) -> None:
    metric_keys = [m for m, _ in KEY_METRICS]
    metric_lbls = [l for _, l in KEY_METRICS]
    col_labels  = [c.replace("pct_", "").replace("_", " ") for c in CONFIGS_ORDER]

    nmetrics = len(KEY_METRICS)
    fig_h = 3.5 + nmetrics * 0.9
    fig, axes = plt.subplots(2, 1, figsize=(11, fig_h), gridspec_kw={"hspace": 0.4})
    fig.patch.set_facecolor("white")

    for var, ax in zip(VARIANTS, axes):
        nrows = len(KEY_METRICS)
        ncols = len(CONFIGS_ORDER)
        ax.set_xlim(0, ncols)
        ax.set_ylim(0, nrows)
        ax.set_aspect("equal")
        ax.invert_yaxis()

        for ri, m in enumerate(metric_keys):
            for ci, cfg in enumerate(CONFIGS_ORDER):
                match = results[
                    (results["variant"] == var) &
                    (results["config"]  == cfg) &
                    (results["metric"]  == m)
                ]
                if match.empty:
                    fc, txt, tc = "#F5F5F5", "—", "#AAAAAA"
                else:
                    r   = match.iloc[0]
                    sig = r["sig_label"]
                    fc  = SIG_COLORS[sig]
                    d   = f"{r['mean_delta']:+.1f}pp" if r["mean_delta"] is not None else ""
                    txt = f"{sig}\n{d}"
                    tc  = "#085041" if sig != "ns" else "#888780"

                rect = mpatches.FancyBboxPatch(
                    (ci + 0.04, ri + 0.04), 0.92, 0.92,
                    boxstyle="round,pad=0.02", linewidth=0, facecolor=fc
                )
                ax.add_patch(rect)
                ax.text(
                    ci + 0.5, ri + 0.5, txt,
                    ha="center", va="center", fontsize=7.5, color=tc,
                    fontweight="bold" if sig != "ns" else "normal",
                    linespacing=1.4
                )

        ax.set_xticks(np.arange(ncols) + 0.5)
        ax.set_xticklabels(col_labels, fontsize=8, rotation=20, ha="right")
        ax.set_yticks(np.arange(nrows) + 0.5)
        ax.set_yticklabels(metric_lbls, fontsize=8)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(VARIANT_LABELS[var], fontsize=10, fontweight="bold", pad=8, loc="left")

    legend_items = [
        mpatches.Patch(facecolor=SIG_COLORS["p<0.01"], label="p < 0.01"),
        mpatches.Patch(facecolor=SIG_COLORS["p<0.05"], label="p < 0.05"),
        mpatches.Patch(facecolor=SIG_COLORS["p<0.10"], label="p < 0.10"),
        mpatches.Patch(facecolor=SIG_COLORS["ns"], label="ns",
                       edgecolor="#CCCCCC", linewidth=0.5),
    ]
    fig.legend(handles=legend_items, loc="lower center", ncol=4, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.text(
        0.5, -0.05,
        "Wilcoxon signed-rank on per-thread deltas vs baseline, pooled across all 3 threads (n=9 per cell).\n"
        "Delta = variant run value minus thread baseline mean. pp = percentage points.",
        ha="center", fontsize=7, color="#888780"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(out_path), dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[OUTPUT] Heatmap saved to {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Pooled delta analysis from convai simulation CSVs.")
    parser.add_argument("--per_run",  default="convai/results_per_run.csv",
                        help="Per-run CSV (default: convai/results_per_run.csv)")
    parser.add_argument("--csv_out",  default="convai/results_pooled_delta.csv",
                        help="Output CSV (default: convai/results_pooled_delta.csv)")
    parser.add_argument("--plot_out", default="convai/plots/pooled_delta_heatmap.pdf",
                        help="Output PDF heatmap (default: convai/plots/pooled_delta_heatmap.pdf)")
    args = parser.parse_args()

    per_run = pd.read_csv(args.per_run)
    print(f"[INFO] Loaded {len(per_run)} per-run rows from {args.per_run}")

    deltas  = compute_deltas(per_run)
    results = run_wilcoxon(deltas)

    print_summary(results)

    csv_out = Path(args.csv_out)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(csv_out, index=False)
    print(f"[OUTPUT] CSV saved to {csv_out}")

    build_heatmap_pdf(results, Path(args.plot_out))


if __name__ == "__main__":
    main()