"""
analyze_simulations.py

Computes per-run and aggregate statistics for convai simulation logs.

Expected directory structure:
  simulator/convai/600/<thread_id>/logs/<run_ts>/convai_agent_<n>.jsonl
  simulator/convai/600/<thread_id>/logs/messages_<ts>.jsonl
  simulator/convai/600/<thread_id>_25pct_cautious/logs/...
  simulator/convai/600_llm/<thread_id>/logs/<run_ts>/convai_llm_agent_<n>.jsonl
  ...

Thread IDs are pure digit strings (e.g. 52494943607412737).
Configs are <thread_id>_<suffix> where suffix is e.g. 25pct_cautious.
Baseline thread_config == thread_id (no suffix).

Outputs:
  <output>                              summary CSV (mean ± std per thread_config per variant)
  <output>_per_run                      one row per run with raw metric values
  <output>_pvalues_variant_vs_baseline  Mann-Whitney p-values: baseline vs each variant config,
                                        separately for 600 and 600_llm

Usage:
  python analyze_simulations.py --base_dir path/to/simulator/convai --output results.csv
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    """Load a .jsonl file, silently skipping malformed lines."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def p_to_stars(p: float | None) -> str:
    """Convert a p-value to a significance star string."""
    if p is None:
        return "n/a"
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


# ---------------------------------------------------------------------------
# Per-run metrics
# ---------------------------------------------------------------------------

def agent_final_states(agent_dir: Path, variant: str) -> dict[str, str]:
    """
    Read every agent file in a run directory.
    Returns {agent_id: final_state} using the last logged 'state' per agent.
    """
    pattern = "convai_llm_agent_*.jsonl" if variant == "600_llm" else "convai_agent_*.jsonl"
    final = {}
    for fpath in agent_dir.glob(pattern):
        agent_id = fpath.stem
        records = load_jsonl(fpath)
        last_state = None
        for rec in records:
            if "state" in rec:
                last_state = rec["state"]
        if last_state is not None:
            final[agent_id] = last_state
    return final


def agent_state_transitions(agent_dir: Path, variant: str) -> dict:
    """
    Track ordered state sequences per agent.
    Returns:
      agents_changed         - int: agents with at least 1 transition
      transition_counts      - dict {(from, to): count}
      transitions_per_agent  - list[int]: transition count per agent
    """
    pattern = "convai_llm_agent_*.jsonl" if variant == "600_llm" else "convai_agent_*.jsonl"
    agents_changed = 0
    transition_counts: dict[tuple, int] = defaultdict(int)
    transitions_per_agent = []

    for fpath in agent_dir.glob(pattern):
        records = load_jsonl(fpath)
        state_seq: list[str] = []
        for rec in records:
            if "state" in rec:
                s = rec["state"]
                if not state_seq or s != state_seq[-1]:
                    state_seq.append(s)

        n_trans = len(state_seq) - 1 if len(state_seq) > 1 else 0
        transitions_per_agent.append(n_trans)
        if n_trans > 0:
            agents_changed += 1
            for i in range(n_trans):
                transition_counts[(state_seq[i], state_seq[i + 1])] += 1

    return {
        "agents_changed": agents_changed,
        "transition_counts": dict(transition_counts),
        "transitions_per_agent": transitions_per_agent,
    }


def max_cycles_from_agents(agent_dir: Path, variant: str) -> float | None:
    """Return the maximum 'cycle' value seen across all agent log entries."""
    pattern = "convai_llm_agent_*.jsonl" if variant == "600_llm" else "convai_agent_*.jsonl"
    max_cycle = None
    for fpath in agent_dir.glob(pattern):
        for rec in load_jsonl(fpath):
            c = rec.get("cycle")
            if c is not None:
                if max_cycle is None or c > max_cycle:
                    max_cycle = c
    return max_cycle


def messages_stats(messages_path: Path) -> dict:
    """Parse the messages file; return total count and state percentages."""
    records = load_jsonl(messages_path)
    total = len(records)
    if total == 0:
        return {"total_messages": 0, "pct_msg_vaccinated": None, "pct_msg_infected": None}

    vaccinated = infected = 0
    for rec in records:
        state = rec.get("variables", {}).get("public", {}).get("state", "")
        if state == "vaccinated":
            vaccinated += 1
        elif state == "infected":
            infected += 1

    return {
        "total_messages": total,
        "pct_msg_vaccinated": 100.0 * vaccinated / total,
        "pct_msg_infected":   100.0 * infected  / total,
    }


# ---------------------------------------------------------------------------
# Discover runs
# ---------------------------------------------------------------------------

def discover_runs(base_dir: Path, variant: str) -> dict[str, list[dict]]:
    """
    Walk base_dir/<variant>/<thread_config>/logs/ and pair run directories
    with message files by sort order (first run dir == first messages file).

    Returns { thread_config: [ {run_dir, messages_path}, ... ] }
    """
    variant_dir = base_dir / variant
    if not variant_dir.exists():
        return {}

    result = {}
    for tc_dir in sorted(variant_dir.iterdir()):
        if not tc_dir.is_dir():
            continue
        logs_dir = tc_dir / "logs"
        if not logs_dir.exists():
            continue

        run_dirs = sorted(
            [d for d in logs_dir.iterdir()
             if d.is_dir() and re.fullmatch(r"\d+", d.name)],
            key=lambda d: int(d.name),
        )
        msg_files = sorted(
            [f for f in logs_dir.iterdir()
             if f.is_file() and re.fullmatch(r"messages_\d+\.jsonl", f.name)],
            key=lambda f: int(re.search(r"\d+", f.name).group()),
        )

        if len(run_dirs) != len(msg_files):
            print(
                f"[WARNING] {variant}/{tc_dir.name}: "
                f"{len(run_dirs)} run dirs vs {len(msg_files)} message files — "
                "using min(len) pairs"
            )

        pairs = [
            {"run_dir": rd, "messages_path": mf}
            for rd, mf in zip(run_dirs, msg_files)
        ]
        if pairs:
            result[tc_dir.name] = pairs

    return result


# ---------------------------------------------------------------------------
# Compute metrics for one run
# ---------------------------------------------------------------------------

def compute_run_metrics(run_dir: Path, messages_path: Path, variant: str) -> dict:
    """Compute all metrics for a single run."""
    final_states = agent_final_states(run_dir, variant)
    n_agents = len(final_states)

    counts: dict[str, int] = defaultdict(int)
    for s in final_states.values():
        counts[s] += 1

    pct_infected   = 100.0 * counts["infected"]   / n_agents if n_agents else None
    pct_vaccinated = 100.0 * counts["vaccinated"]  / n_agents if n_agents else None
    pct_neutral    = 100.0 * counts["neutral"]     / n_agents if n_agents else None

    denom = counts["vaccinated"] + counts["infected"]
    vax_effectiveness = (100.0 * counts["vaccinated"] / denom) if denom > 0 else None

    trans = agent_state_transitions(run_dir, variant)
    agents_changed     = trans["agents_changed"]
    pct_agents_changed = 100.0 * agents_changed / n_agents if n_agents else None
    avg_trans = (
        float(np.mean(trans["transitions_per_agent"]))
        if trans["transitions_per_agent"] else None
    )

    max_cycles = max_cycles_from_agents(run_dir, variant)
    msg        = messages_stats(messages_path)

    return {
        "n_agents":                  n_agents,
        "pct_infected":              pct_infected,
        "pct_vaccinated":            pct_vaccinated,
        "pct_neutral":               pct_neutral,
        "vax_effectiveness":         vax_effectiveness,
        "max_cycles":                max_cycles,
        "total_messages":            msg["total_messages"],
        "pct_msg_vaccinated":        msg["pct_msg_vaccinated"],
        "pct_msg_infected":          msg["pct_msg_infected"],
        "agents_changed":            agents_changed,
        "pct_agents_changed":        pct_agents_changed,
        "avg_transitions_per_agent": avg_trans,
        "transition_counts":         trans["transition_counts"],
    }


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

SCALAR_METRICS = [
    "pct_infected",
    "pct_vaccinated",
    "pct_neutral",
    "vax_effectiveness",
    "max_cycles",
    "total_messages",
    "pct_msg_vaccinated",
    "pct_msg_infected",
    "pct_agents_changed",
    "avg_transitions_per_agent",
]

ALL_STATES = ["neutral", "infected", "vaccinated"]
ALL_TRANSITIONS = [
    (f, t) for f in ALL_STATES for t in ALL_STATES if f != t
]
ALL_METRIC_KEYS = SCALAR_METRICS + [
    f"trans_{f}_to_{t}" for (f, t) in ALL_TRANSITIONS
]


# ---------------------------------------------------------------------------
# Aggregate across runs
# ---------------------------------------------------------------------------

def aggregate_runs(run_metrics: list[dict]) -> dict:
    """Mean, std, and per-run value list for every metric."""
    agg = {}
    for m in SCALAR_METRICS:
        vals = [r[m] for r in run_metrics if r[m] is not None]
        agg[f"{m}_mean"] = float(np.mean(vals)) if vals else None
        agg[f"{m}_std"]  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        agg[f"{m}_runs"] = vals

    for (f, t) in ALL_TRANSITIONS:
        key = f"trans_{f}_to_{t}"
        vals = [r["transition_counts"].get((f, t), 0) for r in run_metrics]
        agg[f"{key}_mean"] = float(np.mean(vals))
        agg[f"{key}_std"]  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        agg[f"{key}_runs"] = vals

    return agg


# ---------------------------------------------------------------------------
# p-value helpers
# ---------------------------------------------------------------------------

def mannwhitney(a: list, b: list) -> float | None:
    """Two-sided Mann-Whitney U; returns p-value or None if not enough data."""
    if len(a) >= 2 and len(b) >= 2:
        try:
            _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            return float(p)
        except Exception:
            pass
    return None


def compute_pvalues_600_vs_llm(agg_600: dict, agg_llm: dict) -> dict:
    """Mann-Whitney between 600 and 600_llm per-run values for every metric."""
    return {
        m: mannwhitney(
            agg_600.get(f"{m}_runs", []),
            agg_llm.get(f"{m}_runs", []),
        )
        for m in ALL_METRIC_KEYS
    }


def compute_pvalues_baseline_vs_variants(
    variant: str,
    thread_id: str,
    all_agg: dict[str, dict[str, dict]],
) -> list[dict]:
    """
    For a given variant ('600' or '600_llm') and thread_id, compare the
    baseline config (thread_id alone) against every suffixed config
    (thread_id_<suffix>) using Mann-Whitney U.

    Returns a list of dicts:
      { variant, thread_id, config (suffix), metric, p_value, stars }
    """
    agg_map = all_agg.get(variant, {})
    if thread_id not in agg_map:
        return []

    baseline_agg = agg_map[thread_id]
    rows = []

    for tc, agg in agg_map.items():
        if tc == thread_id:
            continue
        if not tc.startswith(f"{thread_id}_"):
            continue

        suffix = tc[len(thread_id) + 1:]   # e.g. "25pct_cautious"

        for m in ALL_METRIC_KEYS:
            base_runs    = baseline_agg.get(f"{m}_runs", [])
            variant_runs = agg.get(f"{m}_runs", [])
            p = mannwhitney(base_runs, variant_runs)
            rows.append({
                "variant":   variant,
                "thread_id": thread_id,
                "config":    suffix,
                "metric":    m,
                "p_value":   p,
                "stars":     p_to_stars(p),
            })

    return rows


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def build_summary_rows(
    all_agg:    dict[str, dict[str, dict]],
    pv_600_llm: dict[str, dict],
) -> list[dict]:
    """Flatten aggregated stats + 600-vs-llm p-values into CSV rows."""
    all_tcs: set[str] = set()
    for v in all_agg:
        all_tcs |= set(all_agg[v].keys())

    rows = []
    for tc in sorted(all_tcs):
        for variant, agg_map in all_agg.items():
            if tc not in agg_map:
                continue
            agg = agg_map[tc]
            row: dict = {"variant": variant, "thread_config": tc}
            for m in ALL_METRIC_KEYS:
                row[f"{m}_mean"] = agg.get(f"{m}_mean")
                row[f"{m}_std"]  = agg.get(f"{m}_std")
            rows.append(row)

        if tc in pv_600_llm:
            row = {"variant": "p_value_600_vs_llm", "thread_config": tc}
            for m in ALL_METRIC_KEYS:
                p = pv_600_llm[tc].get(m)
                row[f"{m}_mean"] = p
                row[f"{m}_std"]  = p_to_stars(p)
            rows.append(row)

    return rows


def print_report(all_agg: dict, pv_600_llm: dict) -> None:
    """Pretty-print a human-readable summary to stdout."""
    all_tcs: set[str] = set()
    for v in all_agg:
        all_tcs |= set(all_agg[v].keys())

    for tc in sorted(all_tcs):
        print(f"\n{'='*72}")
        print(f"  Thread/Config: {tc}")
        print(f"{'='*72}")
        print(f"  {'Metric':<42} {'600':>14} {'600_llm':>14} {'p (600vsllm)':>14}")
        print(f"  {'-'*42} {'-'*14} {'-'*14} {'-'*14}")

        for m in ALL_METRIC_KEYS:
            v600 = all_agg.get("600",     {}).get(tc, {})
            vllm = all_agg.get("600_llm", {}).get(tc, {})

            def fmt(agg: dict, key: str) -> str:
                mn = agg.get(f"{key}_mean")
                sd = agg.get(f"{key}_std")
                if mn is None:
                    return "           n/a"
                sd_str = f"+-{sd:.2f}" if (sd is not None and sd != 0.0) else ""
                return f"{mn:>8.2f}{sd_str:<6}"

            p  = pv_600_llm.get(tc, {}).get(m)
            ps = f"{p:.4f} {p_to_stars(p)}" if p is not None else "n/a"
            print(f"  {m:<42} {fmt(v600, m):>14} {fmt(vllm, m):>14} {ps:>14}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze convai simulation logs.")
    parser.add_argument(
        "--base_dir", type=str, default="simulator/convai",
        help="Path to the simulator/convai directory",
    )
    parser.add_argument(
        "--output", type=str, default="simulation_results.csv",
        help="Base path for output CSVs (suffixes added automatically)",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    variants = ["600", "600_llm"]

    all_run_metrics: dict[str, dict[str, list]] = {}
    all_agg:         dict[str, dict[str, dict]] = {}

    # ------------------------------------------------------------------ load
    for variant in variants:
        runs_map = discover_runs(base_dir, variant)
        if not runs_map:
            print(f"[INFO] No runs found for variant '{variant}' under {base_dir}")

        all_run_metrics[variant] = {}
        all_agg[variant]         = {}

        for tc, pairs in runs_map.items():
            print(f"[{variant}] {tc}: {len(pairs)} run(s)")
            run_metrics_list = []
            for i, pair in enumerate(pairs):
                try:
                    m = compute_run_metrics(
                        pair["run_dir"], pair["messages_path"], variant
                    )
                    run_metrics_list.append(m)
                    print(
                        f"  run {i+1}: {pair['run_dir'].name} | "
                        f"agents={m['n_agents']} | "
                        f"inf={m['pct_infected']:.1f}% | "
                        f"vax={m['pct_vaccinated']:.1f}% | "
                        f"msgs={m['total_messages']}"
                    )
                except Exception as e:
                    print(f"  [ERROR] run {i+1} ({pair['run_dir']}): {e}")

            all_run_metrics[variant][tc] = run_metrics_list
            if run_metrics_list:
                all_agg[variant][tc] = aggregate_runs(run_metrics_list)

    # ----------------------------------------- p-values: 600 vs 600_llm
    common_tcs = (
        set(all_agg.get("600", {}).keys()) &
        set(all_agg.get("600_llm", {}).keys())
    )
    pv_600_llm: dict[str, dict] = {
        tc: compute_pvalues_600_vs_llm(
            all_agg["600"][tc], all_agg["600_llm"][tc]
        )
        for tc in common_tcs
    }

    # -------------------------------- p-values: baseline vs variant configs
    all_tcs_all_variants: set[str] = set()
    for v in all_agg:
        all_tcs_all_variants |= set(all_agg[v].keys())

    # Thread IDs are pure digit strings (the baseline configs)
    thread_ids = sorted(
        tc for tc in all_tcs_all_variants if re.fullmatch(r"\d+", tc)
    )

    baseline_pvalue_rows: list[dict] = []
    for variant in variants:
        for thread_id in thread_ids:
            rows = compute_pvalues_baseline_vs_variants(variant, thread_id, all_agg)
            baseline_pvalue_rows.extend(rows)

    # -------------------------------------------------------- print & write
    print_report(all_agg, pv_600_llm)

    out = Path(args.output)

    # summary CSV
    summary_rows = build_summary_rows(all_agg, pv_600_llm)
    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(out, index=False)
        print(f"\n[OUTPUT] Summary written to {out}")
    else:
        print("\n[WARNING] No summary data to write.")

    # per-run detail CSV
    detail_rows = []
    for variant, tc_map in all_run_metrics.items():
        for tc, run_list in tc_map.items():
            for run_i, rm in enumerate(run_list):
                row: dict = {"variant": variant, "thread_config": tc, "run": run_i + 1}
                for m in SCALAR_METRICS:
                    row[m] = rm.get(m)
                for (f, t) in ALL_TRANSITIONS:
                    row[f"trans_{f}_to_{t}"] = rm["transition_counts"].get((f, t), 0)
                detail_rows.append(row)

    if detail_rows:
        detail_path = out.with_stem(out.stem + "_per_run")
        pd.DataFrame(detail_rows).to_csv(detail_path, index=False)
        print(f"[OUTPUT] Per-run details written to {detail_path}")

    # baseline-vs-variant p-values CSV
    if baseline_pvalue_rows:
        pv_path = out.with_stem(out.stem + "_pvalues_variant_vs_baseline")
        pd.DataFrame(baseline_pvalue_rows).to_csv(pv_path, index=False)
        print(f"[OUTPUT] Baseline vs variant p-values written to {pv_path}")


if __name__ == "__main__":
    main()