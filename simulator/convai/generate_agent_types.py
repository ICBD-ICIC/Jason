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
               <original_name>_<pct>pct_<type>_raw.csv  (natural language translation)

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


# ── Natural language personality description ───────────────────────────────────

def _level(value: float, low: float, high: float) -> str:
    """Map a probability value to a low/moderate/high label."""
    if value <= low:
        return "low"
    elif value >= high:
        return "high"
    return "moderate"


def make_personality_description(
    pinf: float,
    pmd:  float,
    pad:  float,
    popi: float,
    prd:  float,
) -> str:
    """
    Produce a second-person prompt directive that blends the five probability
    parameters into a coherent personality sketch.

    Parameter ranges (from PARAM_GRID):
        pinf  in {0.05, 0.10, 0.15}       → low ≤0.05, high ≥0.15
        pmd   in {0.05, 0.10}             → low ≤0.05, high ≥0.10
        pad   in {0.05, 0.10, 0.15}       → low ≤0.05, high ≥0.15
        popi  in {0.10, 0.15, 0.20, 0.25} → low ≤0.10, high ≥0.25
        prd   in {0.10, 0.20, 0.30, 0.40} → low ≤0.10, high ≥0.40
    """

    # ---- pinf: susceptibility to being convinced on first contact ----
    pinf_level = _level(pinf, 0.05, 0.15)
    pinf_phrases = {
        "low":      "You are highly resistant to new claims and rarely change your mind based on a single encounter.",
        "moderate": "You are somewhat open to new information, but a single message is not enough to fully convince you.",
        "high":     "You are quite impressionable and can be convinced by a compelling message on first contact.",
    }

    # ---- pmd: tendency to become sceptical / vaccinated on first contact ----
    pmd_level = _level(pmd, 0.05, 0.10)
    pmd_phrases = {
        "low":      "You do not tend to develop scepticism readily - exposure to a claim does not typically make you dismissive of it.",
        "moderate": "You sometimes develop a critical distance from claims you encounter, becoming harder to persuade thereafter.",
        "high":     "You are quick to become sceptical: once you encounter a claim and resist it, you actively discount it going forward.",
    }

    # ---- pad: willingness to flip opinion when exposed to disagreement ----
    pad_level = _level(pad, 0.05, 0.15)
    pad_phrases = {
        "low":      "When you disagree with a message, you almost never change your position - you hold your ground firmly.",
        "moderate": "Encountering disagreement occasionally causes you to reconsider and adjust your stance.",
        "high":     "You are sensitive to opposing views: disagreement with a message can lead you to adopt the other side's position.",
    }

    # ---- popi: tendency to reinforce one's own opinion ----
    popi_level = _level(popi, 0.10, 0.25)
    popi_phrases = {
        "low":      "Agreement with a message does not particularly strengthen your existing beliefs.",
        "moderate": "When you agree with a message or successfully resist a challenge, your convictions are moderately reinforced.",
        "high":     "Confirmation of your views or resisting a contrary message significantly deepens your commitment to your current position.",
    }

    # ---- prd: how actively you read and process incoming messages ----
    prd_level = _level(prd, 0.10, 0.40)
    prd_phrases = {
        "low":      "You read and process incoming messages slowly, engaging with only a small fraction of what reaches you.",
        "moderate": "You read messages at an average pace, engaging with a reasonable share of the information flow.",
        "high":     "You are a highly active reader who processes a large proportion of incoming messages quickly.",
    }

    paragraph = (
        f"{pinf_phrases[pinf_level]} "
        f"{pmd_phrases[pmd_level]} "
        f"{pad_phrases[pad_level]} "
        f"{popi_phrases[popi_level]} "
        f"{prd_phrases[prd_level]}"
    )
    return paragraph


def make_agent_probs_raw(probs_df: pd.DataFrame) -> pd.DataFrame:
    """
    Translate a per-thread agent_probs DataFrame into natural language
    personality descriptions (one row per agent).

    Columns:
        agent                   - agent identifier
        personality_description - paragraph built from the five prob values only
        state                   - raw value from agent_probs (neutral / infected)
        susceptible             - raw Jason atom from agent_probs (true / false)
        known_conversation      - conversation id for the initiator, empty otherwise
        read_history            - JSON array; source text for initiator, [] for others
    """
    rows = []
    for _, row in probs_df.iterrows():
        description = make_personality_description(
            pinf=float(row["pinf"]),
            pmd=float(row["pmd"]),
            pad=float(row["pad"]),
            popi=float(row["popi"]),
            prd=float(row["prd"]),
        )
        rows.append({
            "agent":                   row["agent"],
            "personality_description": description,
            "state":                   row["state"],
            "susceptible":             row["susceptible"],
            "known_conversation":      row["known_conversation"],
            "read_history":            row["read_history"],
        })
    return pd.DataFrame(
        rows, columns=["agent", "personality_description", "state", "susceptible",
                        "known_conversation", "read_history"]
    )


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
    """Read one base CSV and write all 6 variants plus their raw NL counterparts."""
    df = pd.read_csv(filepath)
    if "known_conversation" in df.columns:
        df["known_conversation"] = df["known_conversation"].astype("Int64")
    # Ensure read_history is treated as a plain string column (JSON arrays).
    # Missing values (e.g. from older files without the column) default to [].
    if "read_history" not in df.columns:
        df["read_history"] = "[]"
    else:
        df["read_history"] = df["read_history"].fillna("[]").astype(str)

    basename = os.path.splitext(os.path.basename(filepath))[0]   # e.g. agent_probs_52499...
    out_dir   = os.path.dirname(filepath)

    # Determine the base name for the corresponding raw file, if it exists.
    # e.g. agent_probs_<id>.csv → agent_probs_raw_<id>.csv
    # Extract the thread-id suffix after "agent_probs_"
    thread_suffix = basename[len("agent_probs_"):]  # e.g. "524991576163250176"
    raw_base_name = f"agent_probs_raw_{thread_suffix}"
    raw_base_path = os.path.join(out_dir, raw_base_name + ".csv")

    has_raw_base = os.path.exists(raw_base_path)
    if has_raw_base:
        raw_base_df = pd.read_csv(raw_base_path)
        # Build a lookup: agent -> {state, susceptible} from the base raw file
        raw_base_lookup = raw_base_df.set_index("agent")[["state", "susceptible"]].to_dict("index")
    else:
        raw_base_lookup = {}

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

            raw_variant_df = make_agent_probs_raw(variant_df)

            raw_out_name = f"agent_probs_raw_{thread_suffix}_{pct}pct_{agent_type}.csv"
            raw_out_path = os.path.join(out_dir, raw_out_name)
            raw_variant_df.to_csv(raw_out_path, index=False)

            print(f"  ✓ {raw_out_name}")


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
        and not any(tag in f for tag in ["cautious", "credulous", "_raw_"])  # skip variants and raw files
    ]

    if not base_files:
        print(f"No base agent_probs CSV files found in:\n  {input_dir}")
        return

    print(f"Found {len(base_files)} base file(s) in {input_dir}")

    for fname in sorted(base_files):
        process_file(os.path.join(input_dir, fname))

    print("\nDone. Generated 6 variants + 6 raw NL files per base file.")
    print("Naming convention:")
    print("  <original>_<pct>pct_<cautious|credulous>.csv")
    print("  agent_probs_raw_<id>_<pct>pct_<cautious|credulous>.csv")


if __name__ == "__main__":
    main()