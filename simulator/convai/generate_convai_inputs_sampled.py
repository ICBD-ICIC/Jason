"""
generate_convai_inputs_sampled.py
=========================
Reads the PHEME-9 dataset and produces simulator input files matching the
real ABSS_CoNVaI Input_Simulator format:

    <output_dir>/
        network.csv                              – one global adjacency list
        public_profiles.csv                      – one global user influence file
        news_sources_corr/
            messages_<thread_id>.csv             – one per sampled thread
            agent_probs_<thread_id>.csv          – one per sampled thread

Global files cover all users/edges across the entire dataset.
Per-thread files cover a random subset of threads whose combined unique
participants reach --num_agents (approximate).

Usage
-----
    python generate_convai_inputs_sampled.py \
        --pheme_path /path/to/pheme-rumour-scheme-dataset \
        --output_dir ./convai_outputs \
        --num_agents 500 \
        --seed 42

Column formats
--------------
network.csv
    from,to,weight
    convai_agent_X,convai_agent_Y,

public_profiles.csv
    agent,attribute,value
    convai_agent_X,pusr,<float>

messages_<thread_id>.csv
    author,content,reactions,original,topics,variables
    convai_agent_X,<tweet_text>,,0,<topic>,{"public":{"conversation_id":<int>,"state":"<state>"}}

agent_probs_<thread_id>.csv
    agent,pinf,pmd,pad,popi,prd,state
    <float>,...,<infected|neutral>

    State assignment (simplified):
        source author (initiator) -> infected
        ALL other agents          -> neutral   (regardless of thread activity)

    Each agent receives a unique random combination drawn from the 288
    CoNVaI parameter combinations defined in Table 4 of the Supplementary
    Material, so this file has one row per agent (plus a header).

Network construction (mirrors the notebook exactly)
    Base graph: all who-follows-whom.dat files across every thread and theme
    are concatenated and read as a directed graph, one edge per line
    (follower_id followed_id).  This reproduces followers_info_adding.graphml
    without needing the pre-built file.
    Augmentation: for every thread, if a participant has no existing path to
    the source author, a directed edge participant -> source_author is added
    (G_full logic from the notebook).

Agent mapping
    Built once from all users across the full dataset, sorted by uid for
    determinism.  convai_agent_1, convai_agent_2, … convai_agent_N.
"""

import argparse
import itertools
import json
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import io

# ---------------------------------------------------------------------------
# CoNVaI parameter grid  (Table 4, Supplementary Material — 288 combinations)
# ---------------------------------------------------------------------------
PARAM_GRID = list(itertools.product(
    [0.05, 0.10, 0.15],
    [0.05, 0.10],
    [0.05, 0.10, 0.15],
    [0.10, 0.15, 0.20, 0.25],
    [0.10, 0.20, 0.30, 0.40],
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log_scaling(value: float, alpha: float) -> float:
    """Equation 1 in the paper: sc(X) = 1 - exp(-alpha * X)."""
    return 1.0 - math.exp(-alpha * value)


def calculate_alpha(median_val: float) -> float:
    """Returns alpha such that sc(median_val) = 0.5."""
    if median_val <= 0:
        return 1.0
    return -math.log(0.5) / median_val


def get_uid(user_dict: dict) -> str:
    """Extract user ID string from a Twitter user dict."""
    return str(user_dict.get("id_str", user_dict.get("id", "")))


def get_thread_uids(thread_df: pd.DataFrame) -> set:
    """Return the set of all unique user IDs that appear in a thread."""
    uids = set()
    for _, row in thread_df.iterrows():
        u = row.get("user")
        if isinstance(u, dict):
            uid = get_uid(u)
            if uid:
                uids.add(uid)
    return uids


def get_source_uid(thread_df: pd.DataFrame) -> str | None:
    """Return the UID of the thread initiator (source tweet author), or None."""
    source_rows = thread_df[thread_df["type_content"] == "source"]
    if source_rows.empty:
        return None
    u = source_rows.iloc[0]["user"]
    if not isinstance(u, dict):
        return None
    uid = get_uid(u)
    return uid if uid else None


# ---------------------------------------------------------------------------
# Load PHEME-9 dataset
# ---------------------------------------------------------------------------

def load_pheme(pheme_path: Path, ann_dir: Path):
    """
    pheme_path : .../threads/en
    ann_dir    : .../annotations
    """
    with open(ann_dir / "en-scheme-annotations.json", "r", encoding="utf-8") as f:
        lines = [l for l in f if not l.strip().startswith("#")]

    ann_all = pd.read_json(
        io.StringIO("".join(lines)),
        lines=True,
        dtype={"tweetid": "int64", "threadid": "int64"},
    )

    annotation_sources = ann_all[ann_all["tweetid"] == ann_all["threadid"]].copy()
    annotation_replies = ann_all[ann_all["tweetid"] != ann_all["threadid"]].copy()
    annotation_replies = annotation_replies.rename(
        columns={"support": "responsetype-vs-source"}
    )

    list_themes = sorted([
        f for f in os.listdir(pheme_path)
        if (pheme_path / f).is_dir()
    ])

    an_lookup = {}
    for theme in list_themes:
        path_el = pheme_path / theme
        for thread_id in os.listdir(path_el):
            ann_file = path_el / thread_id / "annotation.json"
            if ann_file.exists():
                with open(ann_file) as fp:
                    an_lookup[thread_id] = json.load(fp)

    list_dfs = []
    for theme in list_themes:
        path_el = pheme_path / theme
        dir_folders = [
            f for f in os.listdir(path_el)
            if (path_el / f).is_dir() and not f.startswith("a")
        ]
        for thread_id in dir_folders:
            path_thr = path_el / thread_id
            src_dir  = path_thr / "source-tweets"
            reac_dir = path_thr / "reactions"
            rt_file  = path_thr / "retweets.json"

            src_files = list(src_dir.iterdir()) if src_dir.exists() else []
            if not src_files:
                continue

            src_df = pd.read_json(src_files[0], lines=True,
                                  dtype={"id": "int64"})
            src_id = int(src_df["id"].iloc[0])
            src_ann = annotation_sources[
                annotation_sources["tweetid"] == src_id
            ]
            src_df["type_content"] = "source"
            src_df["support"] = (
                src_ann["support"].iloc[0] if len(src_ann) else "underspecified"
            )
            rows = [src_df]

            if reac_dir.exists():
                reac_files = list(reac_dir.iterdir())
                reac_list = []
                for rf in reac_files:
                    try:
                        reac_list.append(
                            pd.read_json(rf, lines=True, dtype={"id": "int64"})
                        )
                    except Exception:
                        pass
                if reac_list:
                    reactions = pd.concat(reac_list, ignore_index=True)
                    reactions["type_content"] = "reaction"

                    def _get_support(tid):
                        try:
                            r = annotation_replies[
                                annotation_replies["tweetid"] == int(tid)
                            ]
                            return (
                                str(r["responsetype-vs-source"].iloc[0])
                                if len(r) else "underspecified"
                            )
                        except Exception:
                            return "underspecified"

                    reactions["support"] = reactions["id"].apply(_get_support)
                    rows.append(reactions)

            if rt_file.exists():
                try:
                    rt_df = pd.read_json(rt_file, lines=True,
                                         dtype={"id": "int64"})
                    if len(rt_df):
                        rt_df["type_content"] = "retweet"
                        rt_df["support"]      = "agreed"
                        rows.append(rt_df)
                except Exception:
                    pass

            thread_df = pd.concat(rows, ignore_index=True)
            meta = an_lookup.get(thread_id, {})
            thread_df["thread_from"]    = thread_id
            thread_df["theme"]          = theme
            thread_df["misinformation"] = meta.get("misinformation", 0)
            thread_df["true"]           = meta.get("true", 0)
            thread_df["is_rumour"]      = meta.get("is_rumour", 0)
            list_dfs.append(thread_df)

    return list_dfs


# ---------------------------------------------------------------------------
# Sample threads until the cumulative unique-agent count reaches num_agents
# ---------------------------------------------------------------------------

def sample_threads_by_agents(list_dfs: list, num_agents: int,
                              seed: int) -> list:
    rng = random.Random(seed)
    shuffled = list_dfs[:]
    rng.shuffle(shuffled)

    selected = []
    seen_uids: set = set()

    for df in shuffled:
        thread_uids = get_thread_uids(df)
        selected.append(df)
        seen_uids |= thread_uids
        if len(seen_uids) >= num_agents:
            break
    else:
        print(
            f"[WARN] Dataset exhausted with only {len(seen_uids):,} unique "
            f"agents (target was {num_agents:,}). Using all threads.",
            file=sys.stderr,
        )

    print(
        f"[INFO] Sampled {len(selected)} threads → "
        f"{len(seen_uids):,} unique agents "
        f"(target ≈ {num_agents:,}, seed={seed})"
    )
    return selected


# ---------------------------------------------------------------------------
# Build adjacency — reachability-based for sampled agents
# ---------------------------------------------------------------------------

def build_adjacency(pheme_path: Path, list_dfs: list,
                    augmentation_dfs: list | None = None,
                    sampled_uids: set | None = None) -> dict:
    import networkx as nx

    if augmentation_dfs is None:
        augmentation_dfs = list_dfs
        
    G = nx.DiGraph()
    list_themes = sorted([
        f for f in os.listdir(pheme_path) if (pheme_path / f).is_dir()
    ])
    dat_count = 0
    for theme in list_themes:
        path_el = pheme_path / theme
        dir_folders = [
            f for f in os.listdir(path_el)
            if (path_el / f).is_dir() and not f.startswith("a")
        ]
        for thread_id in dir_folders:
            dat_file = path_el / thread_id / "who-follows-whom.dat"
            if not dat_file.exists():
                continue
            with open(dat_file, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        G.add_edge(parts[0], parts[1])
                        dat_count += 1

    print(f"[INFO] Base graph from who-follows-whom.dat: "
          f"{G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges "
          f"({dat_count:,} lines read)")

    # G_full augmentation
    for df in augmentation_dfs:
        source_rows = df[df["type_content"] == "source"]
        if source_rows.empty:
            continue
        src_user = source_rows.iloc[0]["user"]
        if not isinstance(src_user, dict):
            continue
        src_uid = get_uid(src_user)
        if not src_uid:
            continue

        for _, row in df.iterrows():
            u = row.get("user")
            if not isinstance(u, dict):
                continue
            uid = get_uid(u)
            if not uid or uid == src_uid:
                continue
            if not G.has_node(uid):
                G.add_node(uid)
            if not G.has_node(src_uid):
                G.add_node(src_uid)
            if not nx.has_path(G, uid, src_uid):
                G.add_edge(uid, src_uid)

    print(f"[INFO] After G_full augmentation: "
          f"{G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    adj: dict = {}

    if sampled_uids is None:
        for u, v in G.edges():
            adj.setdefault(str(u), set()).add(str(v))
    else:
        sampled_uids_str = {str(uid) for uid in sampled_uids}
        print(f"[INFO] Computing reachability between {len(sampled_uids_str):,} "
              f"sampled agents over the full graph…")

        for u, v in G.edges():
            if str(u) in sampled_uids_str and str(v) in sampled_uids_str:
                adj.setdefault(str(u), set()).add(str(v))

        n_edges = sum(len(vs) for vs in adj.values())
        print(f"[INFO] Reachability-based sampled network: "
              f"{len(adj):,} source nodes, {n_edges:,} edges")

    return adj


# ---------------------------------------------------------------------------
# Compute Pusr globally  (Section 4.1)
# ---------------------------------------------------------------------------

def compute_pusr(list_dfs: list) -> dict:
    records = {}
    for df in list_dfs:
        for _, row in df.iterrows():
            u = row.get("user")
            if not isinstance(u, dict):
                continue
            uid = get_uid(u)
            if not uid or uid in records:
                continue
            followers = int(u.get("followers_count", 0))
            followees = int(u.get("friends_count", 0))
            posts     = int(u.get("listed_count", 0))
            verified  = bool(u.get("verified", False))
            ff_ratio  = (followers / followees) if followees > 0 else float(followers)
            records[uid] = {"ff_ratio": ff_ratio, "posts": posts, "verified": verified}

    if not records:
        return {}

    median_ff    = float(np.median([v["ff_ratio"] for v in records.values()]))
    median_posts = float(np.median([v["posts"]    for v in records.values()]))
    alpha_ff     = calculate_alpha(median_ff)    if median_ff    > 0 else 1.0
    alpha_posts  = calculate_alpha(median_posts) if median_posts > 0 else 1.0

    pusr_lookup = {}
    for uid, vals in records.items():
        sc_ff    = log_scaling(vals["ff_ratio"], alpha_ff)
        sc_posts = log_scaling(vals["posts"],    alpha_posts)
        infl     = 0.4 * sc_ff + 0.4 * sc_posts + 0.2 * float(vals["verified"])
        pusr_lookup[uid] = FINFL * infl

    return pusr_lookup


# ---------------------------------------------------------------------------
# Build global agent name mapping  uid -> convai_agent_X
# ---------------------------------------------------------------------------

def build_agent_map(all_uids: set) -> dict:
    return {uid: f"convai_agent_{i+1}"
            for i, uid in enumerate(sorted(all_uids))}


# ---------------------------------------------------------------------------
# Per-thread CSV generators
# ---------------------------------------------------------------------------

def make_messages_csv(thread_df: pd.DataFrame, conversation_id: int,
                      agent_map: dict) -> pd.DataFrame:
    """
    One row per source tweet (the simulation seed).
    The initiator's state is always 'infected'.
    """
    rows = []
    for _, row in thread_df[thread_df["type_content"] == "source"].iterrows():
        u = row.get("user")
        if not isinstance(u, dict):
            continue
        uid    = get_uid(u)
        agent  = agent_map.get(uid, uid)
        text   = str(row.get("text", "")).replace("\n", " ").replace("\r", " ")
        raw_theme = str(row.get("theme", ""))
        topic     = TOPIC_MAP.get(raw_theme, raw_theme)

        # Initiator is always infected
        variables = json.dumps({
            "public": {"conversation_id": conversation_id, "state": "infected"}
        })
        rows.append({
            "author":    agent,
            "content":   text,
            "reactions": "",
            "original":  "",
            "topics":    topic,
            "variables": variables,
        })
    return pd.DataFrame(rows,
                        columns=["author", "content", "reactions",
                                 "original", "topics", "variables"])


def make_agent_probs_csv(thread_df: pd.DataFrame,
                         all_uids: set,
                         agent_map: dict,
                         rng: random.Random) -> pd.DataFrame:
    """
    One row per agent (ordered by agent name).

    State assignment:
        source author (thread initiator) -> infected
        ALL other agents                 -> neutral

    Each agent is assigned a random combination drawn *with replacement* from
    the 288 CoNVaI parameter combinations (PARAM_GRID).

    Columns: agent, pinf, pmd, pad, popi, prd, state
    """
    # Identify the single initiator UID for this thread
    initiator_uid = get_source_uid(thread_df)
    sorted_agents = sorted(agent_map[uid] for uid in all_uids)
    agent_to_uid  = {v: k for k, v in agent_map.items()}

    rows = []
    for agent_name in sorted_agents:
        uid   = agent_to_uid[agent_name]
        state = "infected" if uid == initiator_uid else "neutral"
        pinf, pmd, pad, popi, prd = rng.choice(PARAM_GRID)
        rows.append({
            "agent": agent_name,
            "pinf":  pinf,
            "pmd":   pmd,
            "pad":   pad,
            "popi":  popi,
            "prd":   prd,
            "state": state,
        })

    return pd.DataFrame(rows,
                        columns=["agent", "pinf", "pmd", "pad",
                                 "popi", "prd", "state"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate CoNVaI simulator input files from PHEME-9."
    )
    parser.add_argument("--pheme_path", required=True,
                        help="Root path of the PHEME-9 dataset "
                             "(e.g. /path/to/pheme-rumour-scheme-dataset).")
    parser.add_argument("--output_dir", default="./convai_outputs",
                        help="Root directory for output files.")
    parser.add_argument("--num_agents", type=int, default=None,
                        help=(
                            "Approximate number of unique agents to include. "
                            "Threads are drawn at random (--seed) until the "
                            "cumulative unique-participant count reaches this "
                            "value. If omitted, all threads are used."
                        ))
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for thread sampling and parameter "
                             "assignment (default: 42).")
    args = parser.parse_args()

    # Derive sub-paths from the dataset root
    root_path  = Path(args.pheme_path)
    pheme_path = root_path / "threads" / "en"
    ann_dir    = root_path / "annotations"
    output_dir = Path(args.output_dir)

    for p, label in [
        (root_path,  "root"),
        (pheme_path, "threads/en"),
        (ann_dir,    "annotations"),
    ]:
        if not p.exists():
            print(f"[ERROR] {label} path not found: {p}", file=sys.stderr)
            sys.exit(1)

    rng = random.Random(args.seed)

    print("[INFO] Loading PHEME dataset…")
    list_dfs = load_pheme(pheme_path, ann_dir)          # <-- ann_dir passed explicitly
    print(f"[INFO] Loaded {len(list_dfs)} threads across all events.")

    if args.num_agents is not None:
        print(f"[INFO] Sampling threads to reach ≈{args.num_agents:,} agents "
              f"(seed={args.seed})…")
        selected_dfs = sample_threads_by_agents(
            list_dfs, args.num_agents, args.seed
        )
    else:
        print("[INFO] --num_agents not set; using all threads.")
        selected_dfs = list_dfs

    sampled_uids: set | None = None
    if args.num_agents is not None:
        sampled_uids = set()
        for df in selected_dfs:
            sampled_uids |= get_thread_uids(df)
        print(f"[INFO] Sampled UID set: {len(sampled_uids):,} unique agents.")

    print("[INFO] Building adjacency list…")
    adj = build_adjacency(pheme_path, list_dfs, 
                          augmentation_dfs=selected_dfs,
                          sampled_uids=sampled_uids)
    all_uids = (
        sampled_uids
        if sampled_uids is not None
        else set(adj.keys()) | {nb for nbs in adj.values() for nb in nbs}
    )
    print(f"[INFO] Network: {len(all_uids):,} nodes, "
          f"{sum(len(v) for v in adj.values()):,} edges")

    print("[INFO] Building agent name mapping…")
    agent_map = build_agent_map(all_uids)
    print(f"[INFO] Agent map: {len(agent_map):,} users → convai_agent_1 … "
          f"convai_agent_{len(agent_map)}")

    print("[INFO] Computing user influence scores…")
    pusr_lookup = compute_pusr(selected_dfs)
    print(f"[INFO] Pusr computed for {len(pusr_lookup):,} users.")

    output_dir.mkdir(parents=True, exist_ok=True)
    thread_dir = output_dir / "news_sources_corr"
    thread_dir.mkdir(parents=True, exist_ok=True)

    print("[INFO] Writing network.csv…")
    with open(output_dir / "network.csv", "w", encoding="utf-8") as f:
        f.write("from,to,weight\n")
        for src in sorted(adj.keys()):
            src_agent = agent_map.get(src, src)
            for tgt in sorted(adj[src]):
                tgt_agent = agent_map.get(tgt, tgt)
                f.write(f"{src_agent},{tgt_agent},\n")
    n_edges = sum(len(v) for v in adj.values())
    print(f"[INFO] network.csv written ({n_edges:,} edges).")

    print("[INFO] Writing public_profiles.csv…")
    profiles_df = pd.DataFrame(
        [{"agent":     agent_map.get(uid, uid),
          "attribute": "pusr",
          "value":     round(pusr_lookup.get(uid, 0.0), 6)}
         for uid in sorted(all_uids)],
        columns=["agent", "attribute", "value"],
    )
    profiles_df.to_csv(output_dir / "public_profiles.csv", index=False)
    print(f"[INFO] public_profiles.csv written ({len(profiles_df):,} rows).")

    print(f"[INFO] Writing per-thread files for {len(selected_dfs)} threads…")
    for conv_idx, thread_df in enumerate(selected_dfs, start=1):
        thread_id = str(thread_df["thread_from"].iloc[0])
        theme     = str(thread_df["theme"].iloc[0])
        topic     = TOPIC_MAP.get(theme, theme)

        messages_df = make_messages_csv(thread_df, conv_idx, agent_map)
        messages_df.to_csv(thread_dir / f"messages_{thread_id}.csv", index=False)

        probs_df = make_agent_probs_csv(thread_df, all_uids, agent_map, rng)
        probs_df.to_csv(thread_dir / f"agent_probs_{thread_id}.csv", index=False)

        state_counts = probs_df["state"].value_counts()
        n_inf = state_counts.get("infected", 0)
        n_neu = state_counts.get("neutral",  0)
        print(f"  [{conv_idx:3d}/{len(selected_dfs)}] {thread_id} "
              f"({topic}) — Inf={n_inf}, Neu={n_neu}, "
              f"total_agents={len(probs_df)}")

    print(f"\n[DONE] Outputs written to: {output_dir.resolve()}")
    print(f"  Global : network.csv, public_profiles.csv")
    print(f"  Threads: news_sources_corr/messages_<id>.csv + "
          f"agent_probs_<id>.csv  ({len(selected_dfs)} files each)")
    print(f"\n  State rule: initiator -> infected, all others -> neutral")
    print(f"  agent_probs format: one row per agent, columns = "
          f"agent,pinf,pmd,pad,popi,prd,state")
    print(f"  Each agent's parameters drawn at random from "
          f"{len(PARAM_GRID)} combinations (seed={args.seed}).")


if __name__ == "__main__":
    main()