"""
analyze_simulations.py

Computes per-run and aggregate statistics for convai simulation logs.

Expected directory structure:
  simulator/convai/600/<thread_id>/logs/<run_ts>/convai_agent_<n>.jsonl
  simulator/convai/600/<thread_id>/logs/messages_<ts>.jsonl
  simulator/convai/600/<thread_id>_25pct_cautious/logs/...
  simulator/convai/600_llm/<thread_id>/logs/<run_ts>/convai_llm_agent_<n>.jsonl
  ...

Thread IDs are pure digit strings.
Baseline thread_config == thread_id (no suffix).
Variant configs are <thread_id>_<suffix>.

Outputs:
  <output>                             summary CSV (mean ± std per thread_config per variant)
  <output>_per_run                     one row per run with raw metric values
  <output>_pvalues_variant_vs_baseline Mann-Whitney p-values: baseline vs each variant config,
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

# Susceptible agent counts per thread (hardcoded)
SUSCEPTIBLES = {
    "524922729485848576": 108,
    "524949443607412737": 236,
    "524990163446140928": 494,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
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


def p_to_stars(p) -> str:
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


def cycles_from_agents(agent_dir: Path, variant: str) -> tuple[float | None, float | None]:
    pattern = "convai_llm_agent_*.jsonl" if variant == "600_llm" else "convai_agent_*.jsonl"
    all_max_per_agent: list[int] = []
    global_max = None

    for fpath in agent_dir.glob(pattern):
        agent_max = None
        for rec in load_jsonl(fpath):
            c = rec.get("cycle")
            if c is not None:
                if global_max is None or c > global_max:
                    global_max = c
                if agent_max is None or c > agent_max:
                    agent_max = c
        if agent_max is not None:
            all_max_per_agent.append(agent_max)

    avg_cycle = float(np.mean(all_max_per_agent)) if all_max_per_agent else None
    return global_max, avg_cycle


def messages_stats(messages_path: Path) -> dict:
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

def compute_run_metrics(run_dir: Path, messages_path: Path, variant: str, thread_id: str) -> dict:
    final_states = agent_final_states(run_dir, variant)
    n_agents = len(final_states)

    counts: dict[str, int] = defaultdict(int)
    for s in final_states.values():
        counts[s] += 1

    n_susceptible = SUSCEPTIBLES.get(thread_id)

    pct_infected_total     = 100.0 * counts["infected"]   / n_agents if n_agents else None
    pct_vaccinated_total   = 100.0 * counts["vaccinated"]  / n_agents if n_agents else None
    pct_infected_susc      = 100.0 * counts["infected"]   / n_susceptible if n_susceptible else None
    pct_vaccinated_susc    = 100.0 * counts["vaccinated"]  / n_susceptible if n_susceptible else None

    denom = counts["vaccinated"] + counts["infected"]
    vax_effectiveness_total = (100.0 * counts["vaccinated"] / denom) if denom > 0 else None

    denom_susc = min(counts["vaccinated"] + counts["infected"], n_susceptible) if n_susceptible else denom
    vax_effectiveness_susc = (100.0 * counts["vaccinated"] / denom_susc) if denom_susc > 0 else None

    trans = agent_state_transitions(run_dir, variant)
    total_transitions = sum(trans["transition_counts"].values())

    max_cycles, avg_cycles = cycles_from_agents(run_dir, variant)
    msg = messages_stats(messages_path)

    # Transition % of total transitions
    def trans_pct(f, t):
        return 100.0 * trans["transition_counts"].get((f, t), 0) / total_transitions if total_transitions else 0.0

    return {
        "n_agents":                   n_agents,
        "n_susceptible":              n_susceptible,
        # Final state % from total agents
        "pct_infected_total":         pct_infected_total,
        "pct_vaccinated_total":       pct_vaccinated_total,
        # Final state % from susceptibles
        "pct_infected_susc":          pct_infected_susc,
        "pct_vaccinated_susc":        pct_vaccinated_susc,
        # Vaccination effectiveness
        "vax_effectiveness_total":    vax_effectiveness_total,
        "vax_effectiveness_susc":     vax_effectiveness_susc,
        # Cycles
        "max_cycles":                 max_cycles,
        "avg_cycles":                 avg_cycles,
        # Messages
        "total_messages":             msg["total_messages"],
        "pct_msg_vaccinated":         msg["pct_msg_vaccinated"],
        "pct_msg_infected":           msg["pct_msg_infected"],
        # Key transitions (% of total transitions)
        "trans_neutral_to_infected":  trans_pct("neutral",    "infected"),
        "trans_neutral_to_vaccinated":trans_pct("neutral",    "vaccinated"),
        "trans_infected_to_vaccinated":trans_pct("infected",  "vaccinated"),
        "trans_vaccinated_to_infected":trans_pct("vaccinated","infected"),
        # Raw transition counts (for message rate scatter)
        "trans_counts_raw":           {f"{f}_to_{t}": v for (f, t), v in trans["transition_counts"].items()},
        # Messages per cycle (for rate-over-time)
        "messages_per_cycle":         (msg["total_messages"] / max_cycles) if (max_cycles and max_cycles > 0) else None,
    }


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

SCALAR_METRICS = [
    "pct_infected_total",
    "pct_vaccinated_total",
    "pct_infected_susc",
    "pct_vaccinated_susc",
    "vax_effectiveness_total",
    "vax_effectiveness_susc",
    "max_cycles",
    "avg_cycles",
    "total_messages",
    "pct_msg_vaccinated",
    "pct_msg_infected",
    "trans_neutral_to_infected",
    "trans_neutral_to_vaccinated",
    "trans_infected_to_vaccinated",
    "trans_vaccinated_to_infected",
    "messages_per_cycle",
]

KEY_TRANSITIONS = [
    "trans_neutral_to_infected",
    "trans_neutral_to_vaccinated",
    "trans_infected_to_vaccinated",
    "trans_vaccinated_to_infected",
]


# ---------------------------------------------------------------------------
# Aggregate across runs
# ---------------------------------------------------------------------------

def aggregate_runs(run_metrics: list[dict]) -> dict:
    agg = {}
    for m in SCALAR_METRICS:
        vals = [r[m] for r in run_metrics if r.get(m) is not None]
        agg[f"{m}_mean"] = float(np.mean(vals)) if vals else None
        agg[f"{m}_std"]  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        agg[f"{m}_runs"] = vals
    return agg


# ---------------------------------------------------------------------------
# p-value helpers
# ---------------------------------------------------------------------------

def mannwhitney(a: list, b: list):
    if len(a) >= 2 and len(b) >= 2:
        try:
            _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            return float(p)
        except Exception:
            pass
    return None


def compute_pvalues_baseline_vs_variants(
    variant: str,
    thread_id: str,
    all_agg: dict[str, dict[str, dict]],
) -> list[dict]:
    agg_map = all_agg.get(variant, {})
    if thread_id not in agg_map:
        return []

    baseline_agg = agg_map[thread_id]
    rows = []

    for tc, agg in agg_map.items():
        if tc == thread_id or not tc.startswith(f"{thread_id}_"):
            continue
        suffix = tc[len(thread_id) + 1:]

        for m in SCALAR_METRICS:
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

def build_summary_rows(all_agg: dict[str, dict[str, dict]]) -> list[dict]:
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
            for m in SCALAR_METRICS:
                row[f"{m}_mean"] = agg.get(f"{m}_mean")
                row[f"{m}_std"]  = agg.get(f"{m}_std")
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze convai simulation logs.")
    parser.add_argument("--base_dir", type=str, default="convai")
    parser.add_argument("--output",   type=str, default="convai/results.csv")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    variants = ["600", "600_llm"]

    all_run_metrics: dict[str, dict[str, list]] = {}
    all_agg:         dict[str, dict[str, dict]] = {}

    for variant in variants:
        runs_map = discover_runs(base_dir, variant)
        if not runs_map:
            print(f"[INFO] No runs found for variant '{variant}' under {base_dir}")

        all_run_metrics[variant] = {}
        all_agg[variant]         = {}

        for tc, pairs in runs_map.items():
            # Extract thread_id (pure digit prefix of tc)
            thread_id = tc.split("_")[0]
            print(f"[{variant}] {tc}: {len(pairs)} run(s)")
            run_metrics_list = []
            for i, pair in enumerate(pairs):
                try:
                    m = compute_run_metrics(
                        pair["run_dir"], pair["messages_path"], variant, thread_id
                    )
                    run_metrics_list.append(m)
                    print(
                        f"  run {i+1}: agents={m['n_agents']} | "
                        f"susc={m['n_susceptible']} | "
                        f"inf_susc={m['pct_infected_susc']:.1f}% | "
                        f"vax_susc={m['pct_vaccinated_susc']:.1f}% | "
                        f"msgs={m['total_messages']} | "
                        f"max_cycles={m['max_cycles']}"
                    )
                except Exception as e:
                    print(f"  [ERROR] run {i+1} ({pair['run_dir']}): {e}")

            all_run_metrics[variant][tc] = run_metrics_list
            if run_metrics_list:
                all_agg[variant][tc] = aggregate_runs(run_metrics_list)

    # p-values: baseline vs variant configs only
    all_tcs_all_variants: set[str] = set()
    for v in all_agg:
        all_tcs_all_variants |= set(all_agg[v].keys())

    thread_ids = sorted(
        tc for tc in all_tcs_all_variants if re.fullmatch(r"\d+", tc)
    )

    baseline_pvalue_rows: list[dict] = []
    for variant in variants:
        for thread_id in thread_ids:
            rows = compute_pvalues_baseline_vs_variants(variant, thread_id, all_agg)
            baseline_pvalue_rows.extend(rows)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    summary_rows = build_summary_rows(all_agg)
    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(out, index=False)
        print(f"\n[OUTPUT] Summary written to {out}")
    else:
        print("\n[WARNING] No summary data to write.")

    detail_rows = []
    for variant, tc_map in all_run_metrics.items():
        for tc, run_list in tc_map.items():
            for run_i, rm in enumerate(run_list):
                row: dict = {"variant": variant, "thread_config": tc, "run": run_i + 1}
                for m in SCALAR_METRICS:
                    row[m] = rm.get(m)
                detail_rows.append(row)

    if detail_rows:
        detail_path = out.with_stem(out.stem + "_per_run")
        pd.DataFrame(detail_rows).to_csv(detail_path, index=False)
        print(f"[OUTPUT] Per-run details written to {detail_path}")

    if baseline_pvalue_rows:
        pv_path = out.with_stem(out.stem + "_pvalues_variant_vs_baseline")
        pd.DataFrame(baseline_pvalue_rows).to_csv(pv_path, index=False)
        print(f"[OUTPUT] Baseline vs variant p-values written to {pv_path}")


if __name__ == "__main__":
    main()