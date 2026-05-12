"""
generate_agent_types.py
=======================
Reads the 3 base agent_probs CSV files and generates 6 nudged variants per file:
  - 25%, 50%, 75% cautious
  - 25%, 50%, 75% credulous

Cautious agents:  pinf x 0.5,  pmd x 1.5,  pad x 0.5
Credulous agents: pinf x 1.5,  pmd x 0.5,  pad x 1.5

All nudged values are clipped to stay within the original paper's PARAM_GRID bounds:
  pinf: [0.05, 0.15]
  pmd:  [0.05, 0.10]
  pad:  [0.05, 0.15]
  popi: [0.10, 0.25]  (untouched, bounds kept for reference)
  prd:  [0.10, 0.40]  (untouched, bounds kept for reference)

Agent selection per condition: independent random draw (fixed seed per condition).
Output naming: <original_name>_<pct>pct_<type>.csv

Usage
-----
    # Use default path (datasets/convai-selected/news_sources_corr/ relative to script)
    python generate_agent_types.py
 
    # Specify input directory explicitly
    python generate_agent_types.py --input_dir /path/to/news_sources_corr
"""

import argparse
import os
import numpy as np
import pandas as pd

PERCENTAGES = [25, 50, 75]

# Multiplicative nudge factors per agent type
NUDGE_FACTORS = {
    "cautious":  {"pinf": 0.5, "pmd": 1.5, "pad": 0.5},
    "credulous": {"pinf": 1.5, "pmd": 0.5, "pad": 1.5},
}

# Clip bounds from original PARAM_GRID (only for nudged probs)
CLIP_BOUNDS = {
    "pinf": (0.05, 0.15),
    "pmd":  (0.05, 0.10),
    "pad":  (0.05, 0.15),
}

# Seeds: one per (percentage, agent_type) combination — fully reproducible
# Layout: SEEDS[(pct, agent_type)] = int
SEEDS = {
    (25, "cautious"):  100,
    (50, "cautious"):  200,
    (75, "cautious"):  300,
    (25, "credulous"): 400,
    (50, "credulous"): 500,
    (75, "credulous"): 600,
}

# ── Core functions ─────────────────────────────────────────────────────────────

def nudge_agent(row: pd.Series, agent_type: str) -> pd.Series:
    """Apply multiplicative nudge to a single agent row, clipped to grid bounds."""
    row = row.copy()
    factors = NUDGE_FACTORS[agent_type]
    for prob, factor in factors.items():
        lo, hi = CLIP_BOUNDS[prob]
        row[prob] = round(float(np.clip(row[prob] * factor, lo, hi)), 4)
    return row


def generate_variant(df: pd.DataFrame, pct: int, agent_type: str) -> pd.DataFrame:
    """
    Create a copy of df where `pct`% of agents are nudged to `agent_type`.
    Selection is an independent random draw using a fixed seed.
    """
    rng = np.random.default_rng(SEEDS[(pct, agent_type)])
    n_agents = len(df)
    n_convert = round(n_agents * pct / 100)

    selected_indices = rng.choice(n_agents, size=n_convert, replace=False)
    selected_indices_set = set(selected_indices)

    new_rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        if i in selected_indices_set:
            new_rows.append(nudge_agent(row, agent_type))
        else:
            new_rows.append(row.copy())

    result = pd.DataFrame(new_rows, columns=df.columns)
    return result


def process_file(filepath: str) -> None:
    """Read one base CSV and write all 6 variants."""
    df = pd.read_csv(filepath)
    basename = os.path.splitext(os.path.basename(filepath))[0]   # e.g. agent_probs_52499...
    out_dir   = os.path.dirname(filepath)

    print(f"\nProcessing: {basename}")
    print(f"  Agents: {len(df)}")

    for agent_type in ["cautious", "credulous"]:
        for pct in PERCENTAGES:
            variant_df = generate_variant(df, pct, agent_type)

            n_converted = round(len(df) * pct / 100)
            out_name = f"{basename}_{pct}pct_{agent_type}.csv"
            out_path = os.path.join(out_dir, out_name)

            # Preserve lowercase boolean strings to match original CSV format
            out_df = variant_df.copy()
            for col in out_df.select_dtypes(include="bool").columns:
                out_df[col] = out_df[col].map({True: "true", False: "false"})
            out_df.to_csv(out_path, index=False)

            print(f"  ✓ {out_name}  ({n_converted}/{len(df)} agents nudged)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    default_dir = os.path.join(os.path.dirname(__file__), "datasets", "convai-selected", "news_sources_corr")

    parser = argparse.ArgumentParser(
        description="Generate cautious/credulous agent prob variants from base agent_probs CSVs."
    )
    parser.add_argument(
        "--input_dir", default=default_dir,
        help=f"Directory containing base agent_probs_*.csv files (default: {default_dir})"
    )
    args = parser.parse_args()
    input_dir = args.input_dir

    if not os.path.isdir(input_dir):
        print(f"[ERROR] Directory not found: {input_dir}")
        return

    base_files = [
        f for f in os.listdir(input_dir)
        if f.startswith("agent_probs_") and f.endswith(".csv")
        and not any(tag in f for tag in ["cautious", "credulous"])  # skip if re-run
    ]

    if not base_files:
        print(f"No base agent_probs CSV files found in:\n  {input_dir}")
        return

    print(f"Found {len(base_files)} base file(s) in {input_dir}")

    for fname in sorted(base_files):
        process_file(os.path.join(input_dir, fname))

    print("\nDone. Generated 6 variants per base file.")
    print("Naming convention: <original>_<pct>pct_<cautious|credulous>.csv")


if __name__ == "__main__":
    main()