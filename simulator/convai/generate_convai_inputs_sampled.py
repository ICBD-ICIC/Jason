"""
generate_convai_inputs_sampled.py
==================================
Reads the PHEME-9 dataset and produces simulator input files matching the
ABSS_CoNVaI Input_Simulator format.

Usage
-----
    python generate_convai_inputs_sampled.py \
        --pheme_path /path/to/pheme-rumour-scheme-dataset \
        --output_dir ./convai_outputs \
        --seed 42
"""

import argparse
import io
import itertools
import json
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# CoNVaI parameter grid — 288 combinations (Table 4, Supplementary Material)
PARAM_GRID = list(itertools.product(
    [0.05, 0.10, 0.15],   # pinf
    [0.05, 0.10],          # pmd
    [0.05, 0.10, 0.15],   # pad
    [0.10, 0.15, 0.20, 0.25],  # popi
    [0.10, 0.20, 0.30, 0.40],  # prd
))
assert len(PARAM_GRID) == 288

FINFL = 0.1

TOPIC_MAP = {
    "charliehebdo":      "Charlie Hebdo Attack",
    "ebola-essien":      "Ebola Essien Rumour",
    "ferguson":          "Ferguson Unrest",
    "germanwings-crash": "Germanwings Crash",
    "ottawashooting":    "Ottawa Shooting",
    "prince-toronto":    "Prince Toronto",
    "putinmissing":      "Putin Missing",
    "sydneysiege":       "Sydney Siege",
}

# The three Ottawa Shooting threads to simulate
OTTAWA_THREADS = {
    "524991576163250176",
    "524949443607412737",
    "524990163446140928",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log_scaling(value: float, alpha: float) -> float:
    """Equation 1: sc(X) = 1 - exp(-alpha * X)."""
    return 1.0 - math.exp(-alpha * value)


def alpha_from_median(median_val: float) -> float:
    """Returns alpha such that sc(median_val) = 0.5."""
    return -math.log(0.5) / median_val if median_val > 0 else 1.0


def get_uid(user: dict) -> str:
    return str(user.get("id_str") or user.get("id", ""))


def get_source_uid(thread_df: pd.DataFrame) -> str | None:
    src = thread_df[thread_df["type_content"] == "source"]
    if src.empty or not isinstance(src.iloc[0]["user"], dict):
        return None
    uid = get_uid(src.iloc[0]["user"])
    return uid or None


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def _load_annotations(ann_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse en-scheme-annotations.json, return (sources_ann, replies_ann)."""
    with open(ann_dir / "en-scheme-annotations.json", encoding="utf-8") as f:
        lines = [l for l in f if not l.strip().startswith("#")]

    ann = pd.read_json(
        io.StringIO("".join(lines)),
        lines=True,
        dtype={"tweetid": "int64", "threadid": "int64"},
    )
    sources = ann[ann["tweetid"] == ann["threadid"]].copy()
    replies = ann[ann["tweetid"] != ann["threadid"]].copy()
    replies = replies.rename(columns={"support": "responsetype-vs-source"})
    return sources, replies


def _load_single_thread(
    thread_path: Path,
    theme: str,
    ann_sources: pd.DataFrame,
    ann_replies: pd.DataFrame,
    load_meta: bool = False,
) -> pd.DataFrame | None:
    """
    Load one thread directory into a DataFrame.
    Returns None if no source tweet is found.
    """
    src_dir  = thread_path / "source-tweets"
    reac_dir = thread_path / "reactions"
    rt_file  = thread_path / "retweets.json"

    src_files = list(src_dir.iterdir()) if src_dir.exists() else []
    if not src_files:
        return None

    try:
        src_df = pd.read_json(src_files[0], lines=True, dtype={"id": "int64"})
    except Exception:
        return None

    src_id  = int(src_df["id"].iloc[0])
    src_ann = ann_sources[ann_sources["tweetid"] == src_id]
    src_df["type_content"] = "source"
    src_df["support"] = src_ann["support"].iloc[0] if len(src_ann) else "underspecified"
    rows = [src_df]

    # Reactions
    if reac_dir.exists():
        reac_list = []
        for rf in reac_dir.iterdir():
            try:
                reac_list.append(pd.read_json(rf, lines=True, dtype={"id": "int64"}))
            except Exception:
                pass
        if reac_list:
            reactions = pd.concat(reac_list, ignore_index=True)
            reactions["type_content"] = "reaction"

            def _support(tid):
                try:
                    r = ann_replies[ann_replies["tweetid"] == int(tid)]
                    return str(r["responsetype-vs-source"].iloc[0]) if len(r) else "underspecified"
                except Exception:
                    return "underspecified"

            reactions["support"] = reactions["id"].apply(_support)
            rows.append(reactions)

    # Retweets
    if rt_file.exists():
        try:
            rt_df = pd.read_json(rt_file, lines=True, dtype={"id": "int64"})
            if len(rt_df):
                rt_df["type_content"] = "retweet"
                rt_df["support"]      = "agreed"
                rows.append(rt_df)
        except Exception:
            pass

    df = pd.concat(rows, ignore_index=True)
    df["thread_from"] = thread_path.name
    df["theme"]       = theme

    if load_meta:
        ann_file = thread_path / "annotation.json"
        meta = {}
        if ann_file.exists():
            with open(ann_file) as fp:
                meta = json.load(fp)
        df["misinformation"] = meta.get("misinformation", 0)
        df["true"]           = meta.get("true", 0)
        df["is_rumour"]      = meta.get("is_rumour", 0)

    return df


def load_ottawa_threads(pheme_path: Path, ann_dir: Path) -> list[pd.DataFrame]:
    """Load the three Ottawa Shooting threads (with metadata)."""
    ann_sources, ann_replies = _load_annotations(ann_dir)
    ottawa_path = pheme_path / "ottawashooting"
    result = []
    for thread_id in sorted(OTTAWA_THREADS):
        df = _load_single_thread(
            ottawa_path / thread_id, "ottawashooting",
            ann_sources, ann_replies, load_meta=True,
        )
        if df is None:
            print(f"[WARN] No source tweet for thread {thread_id}, skipping.", file=sys.stderr)
        else:
            result.append(df)
    return result


def load_all_threads(pheme_path: Path, ann_dir: Path) -> list[pd.DataFrame]:
    """Load ALL threads across every PHEME-9 event (for global pusr calibration)."""
    ann_sources, ann_replies = _load_annotations(ann_dir)
    result = []
    for theme_dir in sorted(pheme_path.iterdir()):
        if not theme_dir.is_dir():
            continue
        for thread_dir in sorted(theme_dir.iterdir()):
            if not thread_dir.is_dir():
                continue
            df = _load_single_thread(
                thread_dir, theme_dir.name,
                ann_sources, ann_replies, load_meta=False,
            )
            if df is not None:
                result.append(df)
    return result


# ---------------------------------------------------------------------------
# Network / adjacency
# ---------------------------------------------------------------------------

def build_adjacency(pheme_path: Path, ottawa_dfs: list[pd.DataFrame]) -> dict[str, set]:
    """
    Build a directed follower graph for the three Ottawa threads.

    Step 1 — Load who-follows-whom.dat from each thread directory.
    Step 2 — For any reaction/retweet user with no path to the thread
              initiator, add a direct fallback edge.
    """
    import networkx as nx

    G = nx.DiGraph()
    ottawa_path = pheme_path / "ottawashooting"

    for thread_id in OTTAWA_THREADS:
        dat_file = ottawa_path / thread_id / "who-follows-whom.dat"
        if not dat_file.exists():
            print(f"[WARN] {dat_file} not found, skipping.", file=sys.stderr)
            continue
        with open(dat_file, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    G.add_edge(parts[0], parts[1])

    print(f"[INFO] Base graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    for df in ottawa_dfs:
        src_uid = get_source_uid(df)
        if not src_uid:
            continue
        G.add_node(src_uid)
        for _, row in df[df["type_content"].isin(["reaction", "retweet"])].iterrows():
            u = row.get("user")
            if not isinstance(u, dict):
                continue
            uid = get_uid(u)
            if uid and uid != src_uid:
                G.add_node(uid)
                if not nx.has_path(G, uid, src_uid):
                    G.add_edge(uid, src_uid)

    print(f"[INFO] After augmentation: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    adj: dict[str, set] = {}
    for u, v in G.edges():
        adj.setdefault(str(u), set()).add(str(v))
    return adj


# ---------------------------------------------------------------------------
# User influence
# ---------------------------------------------------------------------------

def compute_pusr(all_dfs: list[pd.DataFrame]) -> dict[str, float]:
    """
    Pusr(u) = FINFL * Infl(u)
    Infl(u) = 0.4*sc(ff_ratio) + 0.4*sc(listed_count) + 0.2*verified

    Alpha values are calibrated from the median across ALL threads/events.
    """
    records: dict[str, dict] = {}
    for df in all_dfs:
        for _, row in df.iterrows():
            u = row.get("user")
            if not isinstance(u, dict):
                continue
            uid = get_uid(u)
            if not uid or uid in records:
                continue
            followers = int(u.get("followers_count", 0))
            followees = int(u.get("friends_count",   0))
            records[uid] = {
                "ff_ratio": followers / followees if followees > 0 else float(followers),
                "listed":   int(u.get("listed_count", 0)),
                "verified": bool(u.get("verified", False)),
            }

    if not records:
        return {}

    alpha_ff     = alpha_from_median(float(np.median([v["ff_ratio"] for v in records.values()])))
    alpha_listed = alpha_from_median(float(np.median([v["listed"]   for v in records.values()])))

    return {
        uid: FINFL * (
            0.4 * log_scaling(v["ff_ratio"], alpha_ff) +
            0.4 * log_scaling(v["listed"],   alpha_listed) +
            0.2 * float(v["verified"])
        )
        for uid, v in records.items()
    }


# ---------------------------------------------------------------------------
# Agent mapping
# ---------------------------------------------------------------------------

def build_agent_map(uids: set[str]) -> dict[str, str]:
    """Stable uid -> convai_agent_N mapping (sorted by uid for determinism)."""
    return {uid: f"convai_agent_{i+1}" for i, uid in enumerate(sorted(uids))}


# ---------------------------------------------------------------------------
# Output generators
# ---------------------------------------------------------------------------

def make_messages_csv(
    thread_df: pd.DataFrame,
    conversation_id: int,
    agent_map: dict[str, str],
) -> pd.DataFrame:
    rows = []
    for _, row in thread_df[thread_df["type_content"] == "source"].iterrows():
        u = row.get("user")
        if not isinstance(u, dict):
            continue
        uid   = get_uid(u)
        topic = TOPIC_MAP.get(str(row.get("theme", "")), str(row.get("theme", "")))
        text  = str(row.get("text", "")).replace("\n", " ").replace("\r", " ")
        rows.append({
            "author":    agent_map.get(uid, uid),
            "content":   text,
            "reactions": "",
            "original":  "",
            "topics":    topic,
            "variables": json.dumps({
                "public": {"conversation_id": conversation_id, "state": "infected"}
            }),
        })
    return pd.DataFrame(rows, columns=["author", "content", "reactions",
                                        "original", "topics", "variables"])


def make_agent_probs_csv(
    thread_df: pd.DataFrame,
    all_uids: set[str],
    agent_map: dict[str, str],
    rng: random.Random,
) -> pd.DataFrame:
    initiator_uid = get_source_uid(thread_df)
    agent_to_uid  = {v: k for k, v in agent_map.items()}
    sorted_agents = sorted(agent_map.values(), key=lambda a: int(a.split("_")[-1]))

    rows = []
    for agent in sorted_agents:
        uid   = agent_to_uid[agent]
        state = "infected" if uid == initiator_uid else "neutral"
        pinf, pmd, pad, popi, prd = rng.choice(PARAM_GRID)
        rows.append({
            "agent": agent,
            "pinf":  pinf, "pmd": pmd, "pad": pad, "popi": popi, "prd": prd,
            "state": state,
        })
    return pd.DataFrame(rows, columns=["agent", "pinf", "pmd", "pad", "popi", "prd", "state"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate CoNVaI simulator input files from PHEME-9."
    )
    parser.add_argument("--pheme_path", required=True,
                        help="Root path of the PHEME-9 dataset.")
    parser.add_argument("--output_dir", default="./convai_outputs",
                        help="Root directory for output files.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for parameter assignment (default: 42).")
    args = parser.parse_args()

    root_path  = Path(args.pheme_path)
    pheme_path = root_path / "threads" / "en"
    ann_dir    = root_path / "annotations"
    output_dir = Path(args.output_dir)

    for path, label in [(root_path, "root"), (pheme_path, "threads/en"), (ann_dir, "annotations")]:
        if not path.exists():
            print(f"[ERROR] {label} path not found: {path}", file=sys.stderr)
            sys.exit(1)

    rng = random.Random(args.seed)

    # Load data
    print("[INFO] Loading 3 Ottawa Shooting threads...")
    ottawa_dfs = load_ottawa_threads(pheme_path, ann_dir)
    print(f"[INFO] Loaded {len(ottawa_dfs)} threads.")

    print("[INFO] Loading ALL PHEME-9 threads for global pusr calibration...")
    all_dfs = load_all_threads(pheme_path, ann_dir)
    print(f"[INFO] Loaded {len(all_dfs)} threads across all events.")

    # Build network (Ottawa threads only)
    print("[INFO] Building adjacency list...")
    adj = build_adjacency(pheme_path, ottawa_dfs)
    all_uids = set(adj.keys()) | {nb for nbs in adj.values() for nb in nbs}

    # Global agent map
    agent_map = build_agent_map(all_uids)
    print(f"[INFO] Agent map: {len(agent_map):,} users -> convai_agent_1 … convai_agent_{len(agent_map)}")

    # User influence (all PHEME-9 threads)
    print("[INFO] Computing user influence scores from full dataset...")
    pusr_lookup = compute_pusr(all_dfs)
    print(f"[INFO] Pusr computed for {len(pusr_lookup):,} users.")

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    thread_dir = output_dir / "news_sources_corr"
    thread_dir.mkdir(parents=True, exist_ok=True)

    print("[INFO] Writing network.csv...")
    with open(output_dir / "network.csv", "w", encoding="utf-8") as f:
        f.write("from,to,weight\n")
        for src in sorted(adj):
            src_agent = agent_map.get(src, src)
            for tgt in sorted(adj[src]):
                f.write(f"{src_agent},{agent_map.get(tgt, tgt)},\n")
    print(f"[INFO] network.csv: {sum(len(v) for v in adj.values()):,} edges.")

    print("[INFO] Writing public_profiles.csv...")
    profiles_df = pd.DataFrame(
        [{"agent": agent_map.get(uid, uid), "attribute": "pusr",
          "value": round(pusr_lookup.get(uid, 0.0), 6)}
         for uid in sorted(all_uids)],
        columns=["agent", "attribute", "value"],
    )
    profiles_df.to_csv(output_dir / "public_profiles.csv", index=False)
    print(f"[INFO] public_profiles.csv: {len(profiles_df):,} rows.")

    print(f"[INFO] Writing per-thread files for {len(ottawa_dfs)} threads...")
    for conv_idx, thread_df in enumerate(ottawa_dfs, start=1):
        thread_id = str(thread_df["thread_from"].iloc[0])
        topic     = TOPIC_MAP.get(str(thread_df["theme"].iloc[0]), "")

        make_messages_csv(thread_df, conv_idx, agent_map).to_csv(
            thread_dir / f"messages_{thread_id}.csv", index=False
        )
        probs_df = make_agent_probs_csv(thread_df, all_uids, agent_map, rng)
        probs_df.to_csv(thread_dir / f"agent_probs_{thread_id}.csv", index=False)

        counts = probs_df["state"].value_counts()
        print(f"  [{conv_idx}/{len(ottawa_dfs)}] {thread_id} ({topic}) — "
              f"infected={counts.get('infected', 0)}, neutral={counts.get('neutral', 0)}, "
              f"total={len(probs_df)}")

    print(f"\n[DONE] Output: {output_dir.resolve()}")
    print(f"  Global : network.csv, public_profiles.csv")
    print(f"  Threads: news_sources_corr/messages_<id>.csv + agent_probs_<id>.csv")


if __name__ == "__main__":
    main()