"""
pheme_to_convai.py
==================
Converts one PHEME rumour-scheme (journalism use case) thread into three
CoNVaI input files:

    network.csv          -- agent connections  (from, to, weight)
    messages.csv         -- source tweet only  (author, content, reactions,
                                                original, topics, variables)
    public_profiles.csv  -- Pusr per agent     (agent, attribute, value)

Expected thread layout (PHEME journalism use case from figshare/2068650)
-------------------------------------------------------------------------
    <thread_dir>/
        annotation.json          # contains "is_rumour": "rumour"|"non-rumour"
        source-tweets/
            <tweet_id>.json      # the source tweet (Twitter API object)
        reactions/
            <tweet_id>.json ...  # one file per reply tweet
        who-follows-whom.dat     # "follower_id followee_id" per line
        structure.json           # (not used here)
        retweets.json            # (not used here)

Usage
-----
    python pheme_to_convai.py <thread_dir> [--output_dir <dir>] [--finfl 1.0]

    <thread_dir>  Path to a single numbered thread folder, e.g.:
                  datasets/convai/en/charliehebdo/552783667052167168

Arguments
---------
    --output_dir  Where to write the three CSVs.
                  Default: <thread_dir>/convai_output/
    --finfl       FINFL parameter from the CoNVaI paper (default 1.0).

Output details
--------------
network.csv
    Directed edges read directly from who-follows-whom.dat (follower -> followee).
    Only edges where BOTH endpoints are thread participants are kept.
    Weight column is left empty.

messages.csv
    One row for the source tweet (conversation starter).
    state = "infected"   if annotation.json says is_rumour == "rumour"
    state = "vaccinated" otherwise (non-rumour / unverified)
    variables = {"public": {"conversation_id": 1, "state": "<state>"}}

public_profiles.csv
    Pusr(u) = FINFL * Infl(u)
    Infl(u) = 0.4*sc(followers/followees) + 0.4*sc(posts) + 0.2*verified
    sc(X)   = 1 - exp(-alpha * X),  alpha = 1 / mean(X) across all agents
    Twitter fields used:
        followers  -> followers_count
        followees  -> friends_count   (people the user follows)
        posts      -> listed_count    (number of lists the user appears on)
        verified   -> verified (bool)

Agent naming
------------
Every unique Twitter user_id found in source-tweet + reactions gets a name:
    convai_agent_1, convai_agent_2, ...
ordered by first appearance (source tweet author is always convai_agent_1).
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def sc(x: float, alpha: float) -> float:
    """Scaling function from the paper: 1 - exp(-alpha * x)."""
    return 1.0 - math.exp(-alpha * x)


def alpha_from_mean(values: list) -> float:
    """alpha = 1 / mean; fall back to 1.0 if mean is zero."""
    mean = sum(values) / len(values) if values else 0.0
    return 1.0 / mean if mean > 0 else 1.0


def compute_alphas(users: list) -> dict:
    """Compute alpha for ratio (followers/followees) and posts (listed_count)."""
    ratios = []
    posts  = []
    for u in users:
        followers = u.get("followers_count", 0) or 0
        followees = u.get("friends_count",   1) or 1
        ratios.append(followers / followees)
        posts.append(u.get("listed_count", 0) or 0)
    return {
        "ratio": alpha_from_mean(ratios),
        "posts": alpha_from_mean(posts),
    }


def compute_infl(user: dict, alphas: dict) -> float:
    followers = user.get("followers_count", 0) or 0
    followees = user.get("friends_count",   1) or 1
    posts     = user.get("listed_count",    0) or 0
    verified  = 1.0 if user.get("verified", False) else 0.0
    ratio     = followers / followees
    return (
        0.4 * sc(ratio, alphas["ratio"])
        + 0.4 * sc(posts, alphas["posts"])
        + 0.2 * verified
    )


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_thread(thread_dir: Path):
    """
    Returns:
        source_tweet : dict
        reactions    : list[dict]
        is_rumour    : bool
    """
    # ---- annotation.json ----
    ann_path = thread_dir / "annotation.json"
    if not ann_path.exists():
        raise FileNotFoundError(f"annotation.json not found in {thread_dir}")
    annotation = load_json(ann_path)

    # The journalism use-case annotation.json uses "is_rumour".
    # Value can be "rumour", "non-rumour", 1, 0, True, False ...
    raw = annotation.get("is_rumour", annotation.get("isRumour", ""))
    if isinstance(raw, str):
        is_rumour = raw.strip().lower() == "rumour"
    else:
        is_rumour = bool(raw)

    # ---- source tweet ----
    src_dir = thread_dir / "source-tweets"
    if not src_dir.is_dir():
        raise FileNotFoundError(f"source-tweets/ folder not found in {thread_dir}")
    src_files = sorted(src_dir.glob("*.json"))
    if not src_files:
        raise FileNotFoundError(f"No JSON files inside {src_dir}")
    source_tweet = load_json(src_files[0])

    # ---- reactions ----
    reactions = []
    react_dir = thread_dir / "reactions"
    if react_dir.is_dir():
        for rf in sorted(react_dir.glob("*.json")):
            try:
                reactions.append(load_json(rf))
            except json.JSONDecodeError as e:
                print(f"[warn] Skipping {rf.name}: {e}", file=sys.stderr)

    return source_tweet, reactions, is_rumour


# ---------------------------------------------------------------------------
# Agent map and user lookup
# ---------------------------------------------------------------------------

def get_user_id(tweet: dict) -> str:
    u = tweet.get("user", {})
    return str(u.get("id_str", u.get("id", "")))


def build_agent_map(source_tweet: dict, reactions: list) -> dict:
    """Returns {twitter_user_id_str -> convai_agent_N}, source author first."""
    seen    = {}
    counter = [1]

    def register(uid: str):
        if uid and uid not in seen:
            seen[uid] = f"convai_agent_{counter[0]}"
            counter[0] += 1

    register(get_user_id(source_tweet))
    for t in reactions:
        register(get_user_id(t))
    return seen


def build_user_lookup(source_tweet: dict, reactions: list) -> dict:
    """Returns {twitter_user_id_str -> user_dict}."""
    lookup = {}
    for tweet in [source_tweet] + reactions:
        uid = get_user_id(tweet)
        if uid:
            lookup[uid] = tweet.get("user", {})
    return lookup


# ---------------------------------------------------------------------------
# Network from who-follows-whom.dat
# ---------------------------------------------------------------------------

def load_follow_edges(thread_dir: Path, agent_map: dict) -> list:
    """
    Parse who-follows-whom.dat.
    Each line: <follower_id> <followee_id>  (space or tab separated).
    Only keeps edges where BOTH endpoints are thread participants.
    Returns sorted list of (agent_from, agent_to) tuples.
    """
    dat_path = thread_dir / "who-follows-whom.dat"
    if not dat_path.exists():
        print("[warn] who-follows-whom.dat not found; network.csv will be empty.",
              file=sys.stderr)
        return []

    edges = set()
    with open(dat_path, encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                print(f"[warn] who-follows-whom.dat line {line_no} "
                      f"malformed: {raw!r}", file=sys.stderr)
                continue
            follower_id, followee_id = parts[0], parts[1]
            a_from = agent_map.get(follower_id)
            a_to   = agent_map.get(followee_id)
            if a_from and a_to and a_from != a_to:
                edges.add((a_from, a_to))

    return sorted(edges)


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def write_network(edges: list, out_dir: Path):
    path = out_dir / "network.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from", "to", "weight"])
        for a_from, a_to in edges:
            w.writerow([a_from, a_to, ""])
    print(f"[ok] {path}  ({len(edges)} edges)")


def write_messages(source_tweet: dict, is_rumour: bool,
                   agent_map: dict, out_dir: Path):
    src_uid = get_user_id(source_tweet)
    author  = agent_map.get(src_uid, "convai_agent_1")
    content = source_tweet.get("full_text", source_tweet.get("text", ""))
    state   = "infected" if is_rumour else "vaccinated"
    variables = json.dumps(
        {"public": {"conversation_id": 1, "state": state}},
        ensure_ascii=False,
    )

    path = out_dir / "messages.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["author", "content", "reactions", "original", "topics", "variables"])
        w.writerow([author, content, "", 0, "", variables])
    print(f"[ok] {path}  (1 message, state={state})")


def write_profiles(agent_map: dict, user_lookup: dict,
                   finfl: float, out_dir: Path):
    all_users = list(user_lookup.values())
    alphas    = compute_alphas(all_users)

    path = out_dir / "public_profiles.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["agent", "attribute", "value"])
        for uid, agent_name in agent_map.items():
            user = user_lookup.get(uid, {})
            infl = compute_infl(user, alphas)
            pusr = round(finfl * infl, 6)
            w.writerow([agent_name, "pusr", pusr])
    print(f"[ok] {path}  ({len(agent_map)} agents, FINFL={finfl})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a PHEME journalism-use-case thread to CoNVaI CSVs."
    )
    parser.add_argument(
        "thread_dir",
        help=(
            "Path to a single numbered thread folder, e.g.:\n"
            "  datasets/convai/en/charliehebdo/552783667052167168"
        ),
    )
    parser.add_argument(
        "--output_dir", "-o",
        default=None,
        help="Destination for output CSVs (default: <thread_dir>/convai_output/).",
    )
    parser.add_argument(
        "--finfl",
        type=float,
        default=1.0,
        help="FINFL parameter from the CoNVaI paper (default: 1.0).",
    )
    args = parser.parse_args()

    thread_dir = Path(args.thread_dir)
    if not thread_dir.is_dir():
        sys.exit(f"[error] Not a directory: {thread_dir}")

    out_dir = Path(args.output_dir) if args.output_dir else thread_dir / "convai_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[info] Thread  : {thread_dir.resolve()}")
    print(f"[info] Output  : {out_dir.resolve()}")

    source_tweet, reactions, is_rumour = load_thread(thread_dir)
    print(f"[info] Loaded source tweet + {len(reactions)} reactions | "
          f"rumour={is_rumour}")

    agent_map   = build_agent_map(source_tweet, reactions)
    user_lookup = build_user_lookup(source_tweet, reactions)
    edges       = load_follow_edges(thread_dir, agent_map)

    print(f"[info] {len(agent_map)} unique agents")

    write_network(edges, out_dir)
    write_messages(source_tweet, is_rumour, agent_map, out_dir)
    write_profiles(agent_map, user_lookup, args.finfl, out_dir)

    print("\nDone. Output files:")
    for fname in ("network.csv", "messages.csv", "public_profiles.csv"):
        print(f"  {out_dir / fname}")


if __name__ == "__main__":
    main()