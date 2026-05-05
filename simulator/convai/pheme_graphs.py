#!/usr/bin/env python3
"""
PHEME Ottawa Shooting – Graph Visualizer
=========================================

Actual dataset layout (from ottawashooting/):
  ottawashooting/
    <thread_id>/                      ← threads directly here, no rumours/ subfolder
      source-tweets/
        <tweet_id>.json               ← source tweet (initiator)
      reactions/
        <tweet_id>.json               ← reply tweets (one file each)
      images/                         ← (ignored)
      urls-content/                   ← (ignored)
      annotation.json                 ← veracity + misinformation flags
      retweets.json                   ← retweet objects (one JSON object per line)
      structure.json                  ← reply tree structure
      images.dat                      ← (ignored)
      urls.dat                        ← (ignored)
      who-follows-whom.dat            ← "<userID_A>\t<userID_B>" = A follows B

KEY CHANGE vs original:
  All nodes are now keyed by numeric USER ID (as a string), NOT screen_name.
  This ensures who-follows-whom.dat edges (which use IDs) correctly connect
  to the same nodes extracted from tweet objects.

  Labels on graphs show "<id> (@screen_name)" when the screen_name is known,
  or just the ID when it is not.

Outputs (saved to DATASET_PATH/graphs_output/):
  <thread_id>.pdf   – per-thread PDF with two pages:
                        Page 1: full user + follow graph
                        Page 2: susceptible subgraph (nodes that have a
                                directed path to the initiator in the follow
                                graph, i.e. users who can be reached by the
                                rumour propagating along follow edges)
  all.pdf           – cross-thread graph (one node per thread)

Node colours (per-thread full graph):
  Gold   (#FFD700)  – Initiator: author of the source tweet
  Coral  (#FF6B6B)  – Reactor: appears in reactions/ or retweets.json
  Blue   (#4A90D9)  – Follow-only: in who-follows-whom.dat but not a reactor
  Orchid (#DA70D6)  – Floating: reactor NOT in who-follows-whom.dat (no edges)

Node colours (susceptible subgraph):
  Gold   (#FFD700)  – Initiator
  Green  (#56C55A)  – Susceptible reactor (reactor who can reach the initiator)
  Teal   (#30B8A8)  – Susceptible follow-only user
  (floating nodes are omitted — they have no follow edges)

Arrow colours (cross-thread graph):
  Orange-red – threads share at least one user
  Blue       – a user from thread A follows a user in thread B
"""

from pathlib import Path
import json
import math
import sys

import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages

# ─────────────────────────────────────────────────────────────
# ★  CONFIGURATION  ★
# Change DATASET_PATH to the absolute path of your ottawashooting folder.
# ─────────────────────────────────────────────────────────────
DATASET_PATH = Path("./datasets/pheme-rumour-scheme-dataset/threads/en/ottawashooting")

# Output folder (created automatically inside DATASET_PATH)
OUTPUT_DIR = DATASET_PATH / "graphs_output"

# ─────────────────────────────────────────────────────────────
# Colour palette
# ─────────────────────────────────────────────────────────────
C_INITIATOR   = "#FFD700"   # gold  – source-tweet author
C_REACTOR     = "#FF6B6B"   # coral – replier / retweeter
C_FOLLOW_ONLY = "#4A90D9"   # steel-blue – in follow graph only
C_FLOATING    = "#DA70D6"   # orchid – reactor not in follow graph

C_EDGE_FOLLOW  = "#555555"  # dark grey – A follows B (per-thread)
C_EDGE_SHARED  = "#E8540B"  # orange-red – shared user across threads
C_EDGE_CROSS   = "#2196F3"  # blue – follow relationship across threads

# Susceptible-graph specific colours
C_SUSC_REACTOR = "#56C55A"  # green  – susceptible reactor
C_SUSC_FOLLOW  = "#30B8A8"  # teal   – susceptible follow-only user

# Veracity -> node colour (cross-thread graph)
VERACITY_COLOURS = {
    "true":           "#4CAF50",  # green
    "false":          "#F44336",  # red
    "misinformation": "#F44336",  # red
    "unverified":     "#FF9800",  # amber
    "unknown":        "#9E9E9E",  # grey
}

LEGEND_THREAD = [
    mpatches.Patch(color=C_INITIATOR,   label="Initiator (source-tweet author)"),
    mpatches.Patch(color=C_REACTOR,     label="Reactor (reply / retweet)"),
    mpatches.Patch(color=C_FOLLOW_ONLY, label="In follow graph only"),
    mpatches.Patch(color=C_FLOATING,    label="Reactor not in follow graph (floating)"),
]

LEGEND_GLOBAL = [
    mpatches.Patch(color="#4CAF50",     label="Veracity: True"),
    mpatches.Patch(color="#F44336",     label="Veracity: False / Misinformation"),
    mpatches.Patch(color="#FF9800",     label="Veracity: Unverified"),
    mpatches.Patch(color="#9E9E9E",     label="Veracity: Unknown"),
    mpatches.Patch(color=C_EDGE_SHARED, label="Shared user(s) between threads"),
    mpatches.Patch(color=C_EDGE_CROSS,  label="Follow relationship between threads"),
]

LEGEND_SUSCEPTIBLE = [
    mpatches.Patch(color=C_INITIATOR,   label="Initiator (source-tweet author)"),
    mpatches.Patch(color=C_SUSC_REACTOR, label="Susceptible reactor (has path to initiator)"),
    mpatches.Patch(color=C_SUSC_FOLLOW,  label="Susceptible follow-only user (has path to initiator)"),
]


# ─────────────────────────────────────────────────────────────
# Data loading helpers
# ─────────────────────────────────────────────────────────────

def load_json(path: Path):
    """Load JSON file; return None on any error."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def load_jsonl(path: Path) -> list[dict]:
    """
    Load a file that may contain one JSON object per line (JSON-Lines),
    or a single JSON array / object.  Returns a list of dicts.
    """
    results = []
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read().strip()
        if not raw:
            return results
        # Try as a single JSON value first
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
            if isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            pass
        # Fall back to JSON-Lines (one object per line)
        for line in raw.splitlines():
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        results.append(obj)
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return results


# ── ID / label extraction ────────────────────────────────────

def user_id(tweet_obj) -> str | None:
    """
    Extract the numeric user ID (as a string) from a tweet object.
    Checks both flat dicts and nested {'user': {'id': ...}} format.
    Prefers 'id_str' (lossless) over 'id' (int).
    """
    if not isinstance(tweet_obj, dict):
        return None
    user = tweet_obj.get("user") or {}
    uid = (
        user.get("id_str")
        or str(user.get("id")) if user.get("id") is not None else None
        or tweet_obj.get("id_str")
        or (str(tweet_obj["id"]) if "id" in tweet_obj else None)
    )
    return str(uid) if uid and uid != "None" else None


def user_screen_name(tweet_obj) -> str | None:
    """Extract screen_name from a tweet object (used for labels only)."""
    if not isinstance(tweet_obj, dict):
        return None
    user = tweet_obj.get("user") or {}
    return (
        user.get("screen_name")
        or user.get("name")
        or tweet_obj.get("screen_name")
    )


def make_label(uid: str, id_to_name: dict[str, str]) -> str:
    """
    Human-readable node label: "@screen_name\n(id)" when known,
    otherwise just the (possibly truncated) ID.
    """
    name = id_to_name.get(uid)
    if name:
        display_name = f"@{name}" if not name.startswith("@") else name
        return f"{display_name}\n({uid})"
    # Truncate very long IDs for readability
    return uid if len(uid) <= 14 else f"…{uid[-10:]}"


# ── File loaders ─────────────────────────────────────────────

def load_source_author(thread_dir: Path, id_to_name: dict[str, str]) -> tuple[str | None, str | None]:
    """
    Return (user_id_str, tweet_id) from source-tweets/<id>.json.
    Also populates id_to_name with the screen_name mapping.
    """
    src_dir = thread_dir / "source-tweets"
    if not src_dir.exists():
        return None, None
    for f in sorted(src_dir.glob("*.json")):
        data = load_json(f)
        uid = user_id(data)
        if uid:
            name = user_screen_name(data)
            if name:
                id_to_name[uid] = name
            return uid, f.stem
    return None, None


def load_reactors(thread_dir: Path, id_to_name: dict[str, str]) -> set[str]:
    """
    Collect all user IDs from:
      reactions/<id>.json  – reply tweets (each file = one tweet dict or list)
      retweets.json        – one retweet object per line (JSON-Lines)
    Also populates id_to_name with any screen_name mappings found.
    """
    reactors: set[str] = set()

    def _add(tweet_obj):
        uid = user_id(tweet_obj)
        if uid:
            reactors.add(uid)
            name = user_screen_name(tweet_obj)
            if name:
                id_to_name[uid] = name

    react_dir = thread_dir / "reactions"
    if react_dir.exists():
        for f in react_dir.glob("*.json"):
            data = load_json(f)
            if isinstance(data, list):
                for item in data:
                    _add(item)
            elif isinstance(data, dict):
                _add(data)

    rt_file = thread_dir / "retweets.json"
    if rt_file.exists():
        for obj in load_jsonl(rt_file):
            _add(obj)
            # Also capture retweeted_status author if present
            rt_status = obj.get("retweeted_status")
            if isinstance(rt_status, dict):
                _add(rt_status)

    return reactors


def load_follow_edges(thread_dir: Path) -> list[tuple[str, str]]:
    """
    Parse who-follows-whom.dat.
    Each non-comment line: "<userID_A>\\t<userID_B>"  =>  A follows B.
    Both fields are already numeric user IDs, so no conversion is needed.
    """
    dat = thread_dir / "who-follows-whom.dat"
    edges: list[tuple[str, str]] = []
    if not dat.exists():
        return edges
    with open(dat, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()          # handles tab or space
            if len(parts) >= 2:
                edges.append((str(parts[0]), str(parts[1])))
    return edges


def load_annotation(thread_dir: Path) -> tuple[str, str]:
    """
    Return (veracity_label, category) from annotation.json.
    """
    ann = load_json(thread_dir / "annotation.json")
    if ann is None:
        return "unknown", "unknown"

    veracity = ann.get("veracity") or ann.get("label")
    if veracity:
        veracity = str(veracity).lower()
    else:
        mis = ann.get("misinformation")
        tru = ann.get("true")
        if mis is not None and str(mis) == "1":
            veracity = "misinformation"
        elif tru is not None and str(tru) == "1":
            veracity = "true"
        else:
            veracity = "unverified"

    is_rumour = ann.get("is_rumour")
    if is_rumour is None:
        category = "non-rumour" if veracity == "true" else "rumour"
    else:
        category = "rumour" if is_rumour else "non-rumour"

    return veracity, category


def veracity_badge(veracity: str, category: str) -> str:
    icons = {
        "true":           "VERACITY: True",
        "false":          "VERACITY: False",
        "misinformation": "VERACITY: Misinformation",
        "unverified":     "VERACITY: Unverified",
        "unknown":        "VERACITY: Unknown",
    }
    label = next((v for k, v in icons.items() if k in veracity), f"VERACITY: {veracity}")
    return f"[{category.upper()}]  {label}"


def veracity_colour(veracity: str) -> str:
    for k, c in VERACITY_COLOURS.items():
        if k in veracity:
            return c
    return VERACITY_COLOURS["unknown"]


# ─────────────────────────────────────────────────────────────
# Thread discovery
# ─────────────────────────────────────────────────────────────

def discover_threads(dataset_path: Path) -> list[tuple[str, Path]]:
    SKIP_NAMES = {"images", "graphs_output", "__pycache__", "urls-content"}
    threads = []
    for entry in sorted(dataset_path.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in SKIP_NAMES:
            continue
        is_tweet_id    = entry.name.isdigit()
        has_source     = (entry / "source-tweets").exists()
        has_annotation = (entry / "annotation.json").exists()
        if is_tweet_id or has_source or has_annotation:
            threads.append((entry.name, entry))
    return threads


# ─────────────────────────────────────────────────────────────
# Graph 1 – per-thread user graph
# ─────────────────────────────────────────────────────────────

def build_thread_graph(thread_id: str, thread_dir: Path) -> dict:
    """Collect all data for one thread and return a metadata dict."""
    # id_to_name accumulates id -> screen_name mappings from tweet objects
    id_to_name: dict[str, str] = {}

    author, _     = load_source_author(thread_dir, id_to_name)
    reactors      = load_reactors(thread_dir, id_to_name)
    follow_edges  = load_follow_edges(thread_dir)
    veracity, cat = load_annotation(thread_dir)

    # Author should not also appear as a reactor
    if author:
        reactors.discard(author)

    # Users explicitly mentioned in the follow graph
    follow_users: set[str] = set()
    for a, b in follow_edges:
        follow_users.add(a)
        follow_users.add(b)

    # Reactors with no entry in the follow graph -> "floating" (no edges drawn)
    floating = reactors - follow_users

    # Build directed graph (nodes keyed by user ID string)
    G = nx.DiGraph()
    all_nodes = follow_users | reactors | ({author} if author else set())
    G.add_nodes_from(all_nodes)
    for a, b in follow_edges:
        G.add_edge(a, b)

    # ── Susceptible set ──────────────────────────────────────────────────────
    # A user is "susceptible" if they have a directed path TO the initiator in
    # the follow graph (i.e. the rumour can propagate along follow edges from
    # them to reach the initiator's audience).  Floating nodes have no follow
    # edges at all, so they are excluded by definition.
    # We compute this on the follow-edge subgraph (no floating nodes) so that
    # nx.has_path doesn't accidentally use a zero-hop path for the author itself.
    susceptible: set[str] = set()
    if author and author in G:
        for n in G.nodes():
            if n == author or n in floating:
                continue
            try:
                if nx.has_path(G, n, author):
                    susceptible.add(n)
            except nx.NetworkXError:
                pass

    # Per-node colour & size
    colour_map: dict[str, str] = {}
    size_map:   dict[str, int] = {}
    for n in G.nodes():
        if n == author:
            colour_map[n] = C_INITIATOR
            size_map[n]   = 700
        elif n in floating:
            colour_map[n] = C_FLOATING
            size_map[n]   = 420
        elif n in reactors:
            colour_map[n] = C_REACTOR
            size_map[n]   = 440
        else:
            colour_map[n] = C_FOLLOW_ONLY
            size_map[n]   = 260

    return {
        "thread_id":   thread_id,
        "thread_dir":  thread_dir,
        "veracity":    veracity,
        "category":    cat,
        "author":      author,
        "reactors":    reactors,
        "follow_users": follow_users,
        "floating":    floating,
        "susceptible": susceptible,
        "graph":       G,
        "colour_map":  colour_map,
        "size_map":    size_map,
        "id_to_name":  id_to_name,
        # union of all user sets – used for cross-thread comparison
        "all_users":   all_nodes,
    }


def draw_thread_graph(meta: dict, ax: plt.Axes) -> None:
    G          = meta["graph"]
    floating   = meta["floating"]
    author     = meta["author"]
    tid        = meta["thread_id"]
    id_to_name = meta["id_to_name"]

    if G.number_of_nodes() == 0:
        ax.text(0.5, 0.5, "No data found for this thread",
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        ax.set_title(f"Thread {tid} – no data")
        ax.axis("off")
        return

    # Spring layout for connected nodes; outer ring for floating
    connected = [n for n in G.nodes() if n not in floating]
    float_lst = [n for n in G.nodes() if n in floating]

    pos: dict = {}
    if connected:
        H = G.subgraph(connected)
        try:
            pos.update(nx.spring_layout(H, k=2.8, seed=42, iterations=80))
        except Exception:
            pos.update(nx.random_layout(H, seed=42))

    n_float = len(float_lst)
    if n_float:
        radius = 3.2
        for i, n in enumerate(float_lst):
            angle  = 2 * math.pi * i / n_float
            pos[n] = (radius * math.cos(angle), radius * math.sin(angle))

    node_colors = [meta["colour_map"].get(n, C_FOLLOW_ONLY) for n in G.nodes()]
    node_sizes  = [meta["size_map"].get(n, 260)              for n in G.nodes()]

    nx.draw_networkx_nodes(G, pos, ax=ax,
                           node_color=node_colors, node_size=node_sizes, alpha=0.92)
    nx.draw_networkx_edges(G, pos, ax=ax,
                           edge_color=C_EDGE_FOLLOW,
                           arrows=True, arrowsize=16,
                           width=0.9, alpha=0.65,
                           connectionstyle="arc3,rad=0.08",
                           min_source_margin=12, min_target_margin=12)

    # Labels: show "@screen_name\n(id)" when available, else just id
    labels = {n: make_label(n, id_to_name) for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=6.0)

    follow_only_count = len(
        meta["follow_users"] - meta["reactors"] - ({author} if author else set())
    )
    badge = veracity_badge(meta["veracity"], meta["category"])
    stats = (
        f"Total users: {G.number_of_nodes()}  |  "
        f"Follow-edges: {G.number_of_edges()}  |  "
        f"Reactors: {len(meta['reactors'])}  |  "
        f"Follow-only: {follow_only_count}  |  "
        f"Floating: {len(floating)}"
    )
    ax.set_title(f"Thread {tid}\n{badge}\n{stats}", fontsize=8, pad=10)
    ax.axis("off")


def draw_susceptible_graph(meta: dict, ax: plt.Axes) -> None:
    """
    Draw only the nodes that have a directed path to the initiator in the
    follow graph (plus the initiator itself).  Floating nodes are always
    excluded because they have no follow edges.

    Nodes are coloured with the susceptible palette so the two pages of the
    PDF are visually distinct.
    """
    G           = meta["graph"]
    author      = meta["author"]
    susceptible = meta["susceptible"]
    reactors    = meta["reactors"]
    tid         = meta["thread_id"]
    id_to_name  = meta["id_to_name"]

    # Subgraph: initiator + susceptible nodes only
    keep = susceptible | ({author} if author else set())
    S    = G.subgraph(keep).copy()

    if S.number_of_nodes() == 0 or not author:
        ax.text(
            0.5, 0.5,
            "No susceptible users found\n"
            "(no follow-edge path leads to the initiator)",
            ha="center", va="center", transform=ax.transAxes,
            fontsize=11, color="#666666",
        )
        ax.set_title(f"Thread {tid} – Susceptible subgraph (empty)", fontsize=8)
        ax.axis("off")
        return

    # Layout — spring on the subgraph
    try:
        pos = nx.spring_layout(S, k=2.8, seed=42, iterations=80)
    except Exception:
        pos = nx.random_layout(S, seed=42)

    # Colour & size per node using susceptible palette
    node_colors, node_sizes = [], []
    for n in S.nodes():
        if n == author:
            node_colors.append(C_INITIATOR)
            node_sizes.append(700)
        elif n in reactors:
            node_colors.append(C_SUSC_REACTOR)
            node_sizes.append(440)
        else:
            node_colors.append(C_SUSC_FOLLOW)
            node_sizes.append(260)

    nx.draw_networkx_nodes(S, pos, ax=ax,
                           node_color=node_colors, node_size=node_sizes,
                           alpha=0.92)
    nx.draw_networkx_edges(S, pos, ax=ax,
                           edge_color=C_EDGE_FOLLOW,
                           arrows=True, arrowsize=16,
                           width=0.9, alpha=0.65,
                           connectionstyle="arc3,rad=0.08",
                           min_source_margin=12, min_target_margin=12)

    labels = {n: make_label(n, id_to_name) for n in S.nodes()}
    nx.draw_networkx_labels(S, pos, labels=labels, ax=ax, font_size=6.0)

    n_susc_reactors = len(susceptible & reactors)
    n_susc_follow   = len(susceptible - reactors)
    badge = veracity_badge(meta["veracity"], meta["category"])
    stats = (
        f"Susceptible users: {len(susceptible)}  |  "
        f"of which reactors: {n_susc_reactors}  |  "
        f"follow-only: {n_susc_follow}  |  "
        f"Edges in subgraph: {S.number_of_edges()}"
    )
    ax.set_title(
        f"Thread {tid} – Susceptible subgraph\n{badge}\n{stats}",
        fontsize=8, pad=10,
    )
    ax.axis("off")


def save_thread_pdf(meta: dict, output_dir: Path) -> Path:
    footer = (
        f"PHEME Ottawa Shooting  |  Thread {meta['thread_id']}  "
        f"|  {meta['category'].upper()}  |  Veracity: {meta['veracity']}"
    )
    pdf_path = output_dir / f"{meta['thread_id']}.pdf"
    with PdfPages(pdf_path) as pdf:
        # ── Page 1: full graph ───────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(15, 11))
        draw_thread_graph(meta, ax)
        ax.legend(handles=LEGEND_THREAD, loc="lower left",
                  fontsize=7.5, framealpha=0.85)
        fig.text(0.5, 0.005, footer, ha="center", fontsize=7, color="#666666")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # ── Page 2: susceptible subgraph ─────────────────────────────────────
        fig, ax = plt.subplots(figsize=(15, 11))
        draw_susceptible_graph(meta, ax)
        ax.legend(handles=LEGEND_SUSCEPTIBLE, loc="lower left",
                  fontsize=7.5, framealpha=0.85)
        fig.text(0.5, 0.005, footer + "  |  PAGE 2: Susceptible subgraph",
                 ha="center", fontsize=7, color="#666666")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    return pdf_path


# ─────────────────────────────────────────────────────────────
# Graph 2 – cross-thread graph  (3-page PDF)
#
#   Page 1 – all threads
#   Page 2 – false / misinformation threads only
#   Page 3 – false / misinformation / unverified / unknown threads
#
# Layout is computed once on the full set and reused on every page so
# nodes stay in the same position across pages.
#
# Edge representation:
#   shared-user pairs  → undirected (drawn once per unordered pair) to avoid
#                        the double-arrow clutter that previously appeared when
#                        both A→B and B→A were emitted for the same shared user
#   follow-only pairs  → directed (single arrow, drawn only if no shared edge
#                        already connects the pair in either direction)
# ─────────────────────────────────────────────────────────────

# Veracity groups used for the filtered pages
_FALSE_VERACITIES      = {"false", "misinformation"}
_UNCERTAIN_VERACITIES  = {"false", "misinformation", "unverified", "unknown"}


def build_cross_thread_edges(all_metas: list[dict]) -> dict:
    """
    Returns a dict with two lists:
      'shared' : list of frozenset({tid_a, tid_b})  – unordered pairs that
                 share >= 1 user.  Stored as frozensets so each pair appears
                 exactly once and can be looked up in both directions.
      'follow' : list of (tid_a, tid_b)  – directed pairs where a follower
                 of thread A appears in thread B's user set, and the pair
                 has no shared-user relationship.
    """
    meta_map   = {m["thread_id"]: m for m in all_metas}
    follow_from = {
        tid: {e[0] for e in m["graph"].edges()}
        for tid, m in meta_map.items()
    }

    shared_pairs: set[frozenset] = set()
    follow_pairs: list[tuple]    = []

    tids = [m["thread_id"] for m in all_metas]
    for i, tid_a in enumerate(tids):
        users_a = meta_map[tid_a]["all_users"]
        from_a  = follow_from[tid_a]
        for j, tid_b in enumerate(tids):
            if i == j:
                continue
            users_b = meta_map[tid_b]["all_users"]
            pair    = frozenset({tid_a, tid_b})
            if users_a & users_b:
                shared_pairs.add(pair)
            elif pair not in shared_pairs and from_a & users_b:
                follow_pairs.append((tid_a, tid_b))

    # Remove follow pairs that are now covered by a shared pair
    follow_pairs = [
        (a, b) for a, b in follow_pairs
        if frozenset({a, b}) not in shared_pairs
    ]

    return {"shared": list(shared_pairs), "follow": follow_pairs}


def _build_layout(all_metas: list[dict], cross_edges: dict) -> dict:
    """
    Compute a single node layout over all thread IDs.
    Uses Kamada-Kawai (minimises edge-length variance) when the graph is
    connected enough, otherwise falls back to spring.
    Position is computed on an undirected view to avoid directional bias.
    """
    G = nx.Graph()
    G.add_nodes_from(m["thread_id"] for m in all_metas)
    for pair in cross_edges["shared"]:
        a, b = tuple(pair)
        G.add_edge(a, b)
    for a, b in cross_edges["follow"]:
        if not G.has_edge(a, b):
            G.add_edge(a, b)

    try:
        pos = nx.kamada_kawai_layout(G)
    except Exception:
        try:
            pos = nx.spring_layout(G, k=4.0, seed=42, iterations=120)
        except Exception:
            pos = nx.random_layout(G, seed=42)
    return pos


def _draw_global_ax(
    ax: plt.Axes,
    all_metas: list[dict],
    visible_tids: set[str],
    cross_edges: dict,
    pos: dict,
    title: str,
) -> None:
    """
    Render one page of the cross-thread graph onto *ax*.

    all_metas    – full metadata list (used for node attributes)
    visible_tids – subset of thread IDs to show on this page
    cross_edges  – output of build_cross_thread_edges (full dataset)
    pos          – pre-computed layout (full dataset, reused across pages)
    title        – axes title string
    """
    if not visible_tids:
        ax.text(0.5, 0.5, "No threads to display for this filter.",
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        ax.set_title(title, fontsize=10, pad=10)
        ax.axis("off")
        return

    meta_map = {m["thread_id"]: m for m in all_metas}

    # ── Node attributes ──────────────────────────────────────────────────────
    node_colours, node_sizes, node_labels = [], [], {}
    for tid in visible_tids:
        m       = meta_map.get(tid)
        v       = m["veracity"] if m else "unknown"
        n_users = len(m["all_users"]) if m else 0
        node_colours.append(veracity_colour(v))
        node_sizes.append(max(500, 320 + 24 * n_users))
        short = str(tid)[-8:]
        node_labels[tid] = (
            f"…{short}\n({n_users}u)\n{m['category'] if m else ''}"
        )

    vis_pos = {tid: pos[tid] for tid in visible_tids if tid in pos}

    # Build a simple graph that carries just the visible nodes (no edges needed
    # for drawing nodes/labels — edges are drawn separately below).
    NG = nx.Graph()
    NG.add_nodes_from(visible_tids)

    # Draw nodes
    nx.draw_networkx_nodes(
        NG, vis_pos, ax=ax,
        nodelist=list(visible_tids),
        node_color=node_colours,
        node_size=node_sizes,
        alpha=0.93,
    )
    nx.draw_networkx_labels(
        NG, vis_pos,
        labels=node_labels, ax=ax, font_size=6.5,
    )

    # ── Edges – only between visible nodes ──────────────────────────────────
    # Shared pairs → undirected, one line per pair
    shared_el = [
        tuple(pair) for pair in cross_edges["shared"]
        if pair <= visible_tids          # both endpoints visible
    ]
    # Follow pairs → directed, skip if a shared edge covers the pair
    shared_covered = {frozenset(p) for p in shared_el}
    follow_el = [
        (a, b) for a, b in cross_edges["follow"]
        if a in visible_tids and b in visible_tids
        and frozenset({a, b}) not in shared_covered
    ]

    UG = nx.Graph()
    UG.add_nodes_from(visible_tids)
    if shared_el:
        UG.add_edges_from(shared_el)
        nx.draw_networkx_edges(
            UG, vis_pos, edgelist=shared_el, ax=ax,
            edge_color=C_EDGE_SHARED,
            arrows=False,          # undirected – no arrowheads
            width=2.2, alpha=0.75,
        )

    DG = nx.DiGraph()
    DG.add_nodes_from(visible_tids)
    if follow_el:
        DG.add_edges_from(follow_el)
        nx.draw_networkx_edges(
            DG, vis_pos, edgelist=follow_el, ax=ax,
            edge_color=C_EDGE_CROSS,
            arrows=True, arrowsize=18,
            width=1.1, alpha=0.60,
            connectionstyle="arc3,rad=0.12",
            min_source_margin=14, min_target_margin=14,
        )

    # ── Stats ────────────────────────────────────────────────────────────────
    n_rumour = sum(1 for tid in visible_tids
                   if meta_map.get(tid, {}).get("category") == "rumour")
    n_non    = sum(1 for tid in visible_tids
                   if meta_map.get(tid, {}).get("category") == "non-rumour")

    ax.set_title(
        f"{title}\n"
        f"Threads shown: {len(visible_tids)}  "
        f"(rumours: {n_rumour}, non-rumours: {n_non})  |  "
        f"Shared-user edges: {len(shared_el)}  |  "
        f"Follow edges: {len(follow_el)}",
        fontsize=10, pad=12,
    )
    ax.legend(handles=LEGEND_GLOBAL, loc="upper left", fontsize=8,
              framealpha=0.88)
    ax.axis("off")


def draw_global_graph(all_metas: list[dict], output_dir: Path) -> Path:
    """
    Produce all.pdf with three pages:
      Page 1 – all threads
      Page 2 – false / misinformation threads only
      Page 3 – false / misinformation / unverified / unknown threads
    All pages share the same node positions for easy visual comparison.
    """
    cross_edges = build_cross_thread_edges(all_metas)
    pos         = _build_layout(all_metas, cross_edges)

    all_tids       = {m["thread_id"] for m in all_metas}
    false_tids     = {m["thread_id"] for m in all_metas
                      if m["veracity"] in _FALSE_VERACITIES}
    uncertain_tids = {m["thread_id"] for m in all_metas
                      if m["veracity"] in _UNCERTAIN_VERACITIES}

    footer = (
        "Node size ∝ users in thread  |  Node colour = veracity  "
        "|  Label shows last 8 digits of thread ID  |  "
        "━ shared users (undirected)   → follow-only (directed)"
    )

    pdf_path = output_dir / "all.pdf"
    with PdfPages(pdf_path) as pdf:
        pages = [
            (all_tids,       "PHEME Ottawa Shooting – All Threads"),
            (false_tids,     "PHEME Ottawa Shooting – False & Misinformation Threads"),
            (uncertain_tids, "PHEME Ottawa Shooting – False, Misinformation, Unverified & Unknown Threads"),
        ]
        for tids, title in pages:
            fig, ax = plt.subplots(figsize=(22, 17))
            _draw_global_ax(ax, all_metas, tids, cross_edges, pos, title)
            fig.text(0.5, 0.003, footer, ha="center",
                     fontsize=7.5, color="#666666")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            print(f"  '{title}' → {len(tids)} threads")

    print(f"  Global graph (3 pages) -> {pdf_path}")
    return pdf_path


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def main() -> None:
    dataset_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DATASET_PATH.resolve()

    if not dataset_path.exists():
        print(f"ERROR: Dataset path not found:\n  {dataset_path}")
        print(
            "Edit the DATASET_PATH constant at the top of this script, "
            "or pass the path as a command-line argument:\n"
            "  python pheme_graphs.py /path/to/ottawashooting"
        )
        sys.exit(1)

    output_dir = dataset_path / "graphs_output"
    output_dir.mkdir(exist_ok=True)
    print(f"Dataset : {dataset_path}")
    print(f"Output  : {output_dir}\n")

    threads = discover_threads(dataset_path)
    if not threads:
        print("ERROR: No thread directories found.")
        print(
            "Expected numeric subdirectories (tweet IDs) directly inside the dataset path, "
            "each containing source-tweets/ and annotation.json."
        )
        sys.exit(1)

    print(f"Found {len(threads)} threads. Building graphs...\n")

    all_metas = []
    for idx, (tid, tdir) in enumerate(threads, 1):
        print(f"[{idx:3d}/{len(threads)}]  {tid}", end="  ")
        meta = build_thread_graph(tid, tdir)
        all_metas.append(meta)

        pdf = save_thread_pdf(meta, output_dir)
        G   = meta["graph"]
        print(
            f"nodes={G.number_of_nodes():3d}  "
            f"edges={G.number_of_edges():3d}  "
            f"reactors={len(meta['reactors']):2d}  "
            f"floating={len(meta['floating']):2d}  "
            f"susceptible={len(meta['susceptible']):2d}  "
            f"veracity={meta['veracity']:<14s}  "
            f"-> {pdf.name}"
        )

    print(f"\nBuilding cross-thread graph ({len(all_metas)} threads)...")
    draw_global_graph(all_metas, output_dir)
    print(f"\nDone – {len(all_metas) + 1} PDFs saved to:\n   {output_dir}")


if __name__ == "__main__":
    main()