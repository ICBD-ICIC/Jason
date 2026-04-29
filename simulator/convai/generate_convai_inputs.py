"""
generate_convai_inputs.py
=========================
Reads the PHEME-9 dataset and produces simulator input files matching the
real ABSS_CoNVaI Input_Simulator format:

    <output_dir>/
        network.csv                              – one global adjacency list
        public_profiles.csv                      – one global user influence file
        news_sources_corr/
            messages_<thread_id>.csv             – one per test instance
            agent_probs_<thread_id>.csv          – one per test instance

Global files cover all users/edges across the entire dataset.
Per-thread files cover only the Ottawa Shooting test instances.

Usage
-----
    python generate_convai_inputs.py \
        --phpeme_ath /path/to/pheme-rumour-scheme-dataset/threads/en \
        --output_dir ./convai_outputs

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
    convai_agent_X,<tweet_text>,,0,,{"public":{"conversation_id":<int>,"state":"<state>"}}

agent_probs_<thread_id>.csv
    pinf,pmd,pad,popi,prd,state
    <float>,...,<infected|vaccinated|neutral>

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

State mapping (Section 5.2 of the paper)
    source tweet                    -> infected
    retweet                         -> infected
    reaction agreed/underspecified  -> infected
    reaction disagreed/denied       -> vaccinated
    users absent from this thread   -> neutral

Parameter defaults (mid-range of Table 4, Supplementary Material)
    PINF=0.10  PMD=0.05  PAD=0.10  POPI=0.15  PRD=0.25
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import io

# ---------------------------------------------------------------------------
# CoNVaI default parameters (Table 4, Supplementary Material)
# ---------------------------------------------------------------------------
DEFAULT_PINF = 0.10
DEFAULT_PMD  = 0.05
DEFAULT_PAD  = 0.10
DEFAULT_POPI = 0.15
DEFAULT_PRD  = 0.25

FINFL      = 0.1        # user influence scaling factor (Section 4.1)
TEST_EVENT = "ottawashooting"


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


def annotation_to_state(type_content: str, support: str) -> str:
    """Map tweet type + support annotation to CoNVaI state (Section 5.2)."""
    if type_content in ("source", "retweet"):
        return "infected"
    if str(support).lower() in ("disagreed", "denied"):
        return "vaccinated"
    return "infected"


def get_uid(user_dict: dict) -> str:
    """Extract user ID string from a Twitter user dict."""
    return str(user_dict.get("id_str", user_dict.get("id", "")))


# ---------------------------------------------------------------------------
# Load PHEME-9 dataset
# ---------------------------------------------------------------------------

def load_pheme(pheme_path: Path):
    """
    Returns list_dfs: list of per-thread DataFrames covering all themes.
    Each DataFrame has columns:
        id, user, text, type_content, support, thread_from, theme,
        misinformation, true, is_rumour
    """
    ann_dir = pheme_path.parent.parent / "annotations"

    # Load combined annotation file, skip comment lines starting with #
    with open(ann_dir / "en-scheme-annotations.json", "r", encoding="utf-8") as f:
        lines = [l for l in f if not l.strip().startswith("#")]

    ann_all = pd.read_json(
        io.StringIO("".join(lines)),
        lines=True,
        dtype={"tweetid": "int64", "threadid": "int64"},
    )

    # Sources: where tweetid == threadid
    annotation_sources = ann_all[ann_all["tweetid"] == ann_all["threadid"]].copy()

    # Replies: where tweetid != threadid
    # Rename 'support' to 'responsetype-vs-source' to match what the rest of the script expects
    annotation_replies = ann_all[ann_all["tweetid"] != ann_all["threadid"]].copy()
    annotation_replies = annotation_replies.rename(
        columns={"support": "responsetype-vs-source"}
    )

    list_themes = sorted([
        f for f in os.listdir(pheme_path)
        if (pheme_path / f).is_dir()
    ])

    # Thread-level metadata from annotation.json
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

            # ---- source tweet ----
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

            # ---- reactions ----
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

            # ---- retweets ----
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
# Build global adjacency list  (mirrors G_full in the notebook)
# ---------------------------------------------------------------------------

def build_adjacency(pheme_path: Path, list_dfs: list) -> dict:
    """
    Returns {uid: set(neighbour_uids)}.

    Mirrors the notebook exactly:
    1. Concatenate all who-follows-whom.dat files across every thread and
       theme into one edge list (follower_id followed_id per line) — this
       reproduces the followers_info_adding.graphml base graph.
    2. Augment with G_full logic: for every thread, if a participant has no
       existing path to the source author, add a directed edge
       participant -> source_author.
    """
    import networkx as nx

    # ---- Step 1: read all who-follows-whom.dat files ----
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

    # ---- Step 2: G_full augmentation (notebook logic) ----
    for df in list_dfs:
        source_rows = df[df["type_content"] == "source"]
        if source_rows.empty:
            continue
        src_user = source_rows.iloc[0]["user"]
        if not isinstance(src_user, dict):
            continue
        src_uid = get_uid(src_user)
        if not src_uid:
            continue

        total_conv = df  # all participants in this thread
        for _, row in total_conv.iterrows():
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

    # Convert to adj dict
    adj = {}
    for u, v in G.edges():
        adj.setdefault(str(u), set()).add(str(v))

    return adj


# ---------------------------------------------------------------------------
# Compute Pusr globally across the full dataset  (Section 4.1)
# ---------------------------------------------------------------------------

def compute_pusr(list_dfs: list) -> dict:
    """
    Returns {uid: pusr_value}.
    Pusr(u) = FINFL * Infl(u)
    Infl(u) = 0.4*sc(followers/followees) + 0.4*sc(listed_count) + 0.2*verified
    Alpha values derived from the median across ALL users (cross-event).
    """
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
    """
    Returns {uid: 'convai_agent_N'} for every user in the full dataset.
    Sorted by uid for determinism so the same dataset always produces the
    same mapping.
    """
    return {uid: f"convai_agent_{i+1}"
            for i, uid in enumerate(sorted(all_uids))}


# ---------------------------------------------------------------------------
# Per-thread CSV generators
# ---------------------------------------------------------------------------

def make_messages_csv(thread_df: pd.DataFrame, conversation_id: int,
                      agent_map: dict) -> pd.DataFrame:
    """One row per source tweet (the simulation seed)."""
    rows = []
    for _, row in thread_df[thread_df["type_content"] == "source"].iterrows():
        u = row.get("user")
        if not isinstance(u, dict):
            continue
        uid    = get_uid(u)
        agent  = agent_map.get(uid, uid)
        text   = str(row.get("text", "")).replace("\n", " ").replace("\r", " ")
        state  = annotation_to_state("source", row.get("support", "underspecified"))
        variables = json.dumps({
            "public": {"conversation_id": conversation_id, "state": state}
        })
        rows.append({
            "author":    agent,
            "content":   text,
            "reactions": "",
            "original":  "",
            "topics":    "",
            "variables": variables,
        })
    return pd.DataFrame(rows,
                        columns=["author", "content", "reactions",
                                 "original", "topics", "variables"])


def make_agent_probs_csv(thread_df: pd.DataFrame,
                         all_uids: set,
                         agent_map: dict) -> pd.DataFrame:
    """
    Three-row compact format with a _count column.

    Agents are ordered by their mapped name (convai_agent_N, sorted
    lexicographically — equivalent to sorting by N numerically since all
    names share the same prefix length).

    Row 0 (before):  _count = number of agents whose name is *less than*
                     the initiator's name, state = neutral
    Row 1 (seed):    _count = 1, state = infected
    Row 2 (after):   _count = number of agents whose name is *greater than*
                     the initiator's name, state = neutral

    pinf/pmd/pad/popi/prd are identical on all three rows.
    """
    source_rows = thread_df[thread_df["type_content"] == "source"]
    src_uid = ""
    if not source_rows.empty:
        u = source_rows.iloc[0]["user"]
        if isinstance(u, dict):
            src_uid = get_uid(u)

    src_agent = agent_map.get(src_uid, "") if src_uid else ""

    # Sort agent names the same way the simulator would see them
    sorted_agents = sorted(agent_map[uid] for uid in all_uids)

    if src_agent and src_agent in sorted_agents:
        src_pos      = sorted_agents.index(src_agent)
        count_before = src_pos                            # agents with name < src
        count_after  = len(sorted_agents) - src_pos - 1  # agents with name > src
    else:
        # Fallback: initiator not found — assign all to "before", none after
        count_before = len(sorted_agents)
        count_after  = 0

    base = {
        "pinf": DEFAULT_PINF,
        "pmd":  DEFAULT_PMD,
        "pad":  DEFAULT_PAD,
        "popi": DEFAULT_POPI,
        "prd":  DEFAULT_PRD,
    }

    rows = [
        {**base, "_count": count_before, "state": "neutral"},
        {**base, "_count": 1,            "state": "infected"},
        {**base, "_count": count_after,  "state": "neutral"},
    ]

    return pd.DataFrame(rows,
                        columns=["pinf", "pmd", "pad", "popi", "prd",
                                 "_count", "state"])



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate CoNVaI simulator input files from PHEME-9."
    )
    parser.add_argument("--pheme_path", required=True,
                        help="Path to threads/en inside the PHEME-9 release.")
    parser.add_argument("--output_dir", default="./convai_outputs",
                        help="Root directory for output files.")
    parser.add_argument("--test_event", default=TEST_EVENT,
                        help=f"Event name to treat as test set "
                             f"(default: {TEST_EVENT}).")
    args = parser.parse_args()

    pheme_path = Path(args.pheme_path)
    output_dir = Path(args.output_dir)

    if not pheme_path.exists():
        print(f"[ERROR] PHEME path not found: {pheme_path}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------ load
    print("[INFO] Loading PHEME dataset…")
    list_dfs = load_pheme(pheme_path)
    print(f"[INFO] Loaded {len(list_dfs)} threads across all events.")

    test_dfs = [df for df in list_dfs
                if df["theme"].iloc[0].lower() == args.test_event.lower()]
    print(f"[INFO] Test instances ({args.test_event}): {len(test_dfs)}")

    if not test_dfs:
        available = sorted({df["theme"].iloc[0] for df in list_dfs})
        print(f"[ERROR] No threads found for '{args.test_event}'. "
              f"Available events: {available}", file=sys.stderr)
        sys.exit(1)

    # --------------------------------------------------- global adjacency list
    print("[INFO] Building adjacency list from full dataset…")
    adj = build_adjacency(pheme_path, list_dfs)
    all_uids = set(adj.keys()) | {nb for nbs in adj.values() for nb in nbs}
    print(f"[INFO] Network: {len(all_uids):,} nodes, {len(adj):,} source rows")

    # --------------------------------------------------- global agent mapping
    print("[INFO] Building global agent name mapping…")
    agent_map = build_agent_map(all_uids)
    print(f"[INFO] Agent map: {len(agent_map):,} users → convai_agent_1 … "
          f"convai_agent_{len(agent_map)}")

    # --------------------------------------------------- global user influences
    print("[INFO] Computing user influence scores from full dataset…")
    pusr_lookup = compute_pusr(list_dfs)
    print(f"[INFO] Pusr computed for {len(pusr_lookup):,} users.")

    output_dir.mkdir(parents=True, exist_ok=True)
    thread_dir = output_dir / "news_sources_corr"
    thread_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------- network.csv
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

    # ------------------------------------------------- public_profiles.csv
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

    # ------------------------------------------------- per-thread files
    print("[INFO] Writing per-thread files…")
    for conv_idx, thread_df in enumerate(test_dfs, start=1):
        thread_id = str(thread_df["thread_from"].iloc[0])

        messages_df = make_messages_csv(thread_df, conv_idx, agent_map)
        messages_df.to_csv(
            thread_dir / f"messages_{thread_id}.csv", index=False
        )

        probs_df = make_agent_probs_csv(thread_df, all_uids, agent_map)
        probs_df.to_csv(
            thread_dir / f"agent_probs_{thread_id}.csv", index=False
        )

        counts = probs_df.groupby("state")["_count"].sum()
        n_inf = counts.get("infected", 0)
        n_vac = counts.get("vaccinated", 0)
        n_neu = counts.get("neutral", 0)

        print(f"  [{conv_idx:3d}/{len(test_dfs)}] {thread_id} — "
              f"Inf={n_inf}, Vac={n_vac}, Neu={n_neu}")

    print(f"\n[DONE] Outputs written to: {output_dir.resolve()}")
    print(f"  Global : network.csv, public_profiles.csv")
    print(f"  Threads: news_sources_corr/messages_<id>.csv + "
          f"agent_probs_<id>.csv  ({len(test_dfs)} files each)")


if __name__ == "__main__":
    main()