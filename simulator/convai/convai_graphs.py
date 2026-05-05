#!/usr/bin/env python3
"""
convai_graphs.py
================
Reads the CoNVaI simulator CSV outputs produced by generate_convai_inputs_sampled.py
and generates PDF graphs that mirror the style of pheme_graphs.py.

Outputs (saved inside <output_dir>/graphs_output/):
  <thread_id>.pdf   – 2-page PDF per thread
                        Page 1: full agent graph (all agents + follow edges)
                        Page 2: susceptible subgraph (agents with a directed
                                path to the initiator in the follow graph)
  all.pdf           – cross-thread graph (one node per thread)

Usage
-----
    python convai_graphs.py --output_dir ./convai_outputs

    # or point to a custom directory that already contains the CSVs:
    python convai_graphs.py --output_dir /path/to/convai_outputs
"""

import argparse
import math
import sys
from pathlib import Path

import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd


# ─────────────────────────────────────────────────────────────
# Colour palette  (mirrors pheme_graphs.py)
# ─────────────────────────────────────────────────────────────
C_INITIATOR   = "#FFD700"   # gold   – infected / source agent
C_REACTOR     = "#FF6B6B"   # coral  – agent that appears in thread messages
C_FOLLOW_ONLY = "#4A90D9"   # blue   – in network only, not a message author
C_FLOATING    = "#DA70D6"   # orchid – in agent_probs but has no follow edges

C_EDGE_FOLLOW = "#555555"   # dark grey – follow edge (per-thread)
C_EDGE_SHARED = "#E8540B"   # orange-red – shared agents across threads
C_EDGE_CROSS  = "#2196F3"   # blue       – follow relationship across threads

C_SUSC_REACTOR = "#56C55A"  # green – susceptible reactor
C_SUSC_FOLLOW  = "#30B8A8"  # teal  – susceptible follow-only

VERACITY_COLOURS = {
    "infected":   "#F44336",  # red  – rumour initiator thread
    "neutral":    "#4CAF50",  # green
    "recovered":  "#9E9E9E",  # grey
    "unknown":    "#FF9800",  # amber
}

LEGEND_THREAD = [
    mpatches.Patch(color=C_INITIATOR,   label="Initiator (infected agent)"),
    mpatches.Patch(color=C_REACTOR,     label="Message author (reactor)"),
    mpatches.Patch(color=C_FOLLOW_ONLY, label="In network only (no messages)"),
    mpatches.Patch(color=C_FLOATING,    label="Agent with no follow edges (floating)"),
]

LEGEND_SUSCEPTIBLE = [
    mpatches.Patch(color=C_INITIATOR,    label="Initiator (infected agent)"),
    mpatches.Patch(color=C_SUSC_REACTOR, label="Susceptible reactor (path to initiator)"),
    mpatches.Patch(color=C_SUSC_FOLLOW,  label="Susceptible follow-only (path to initiator)"),
]

LEGEND_GLOBAL = [
    mpatches.Patch(color=C_INITIATOR,   label="Thread with infected initiator"),
    mpatches.Patch(color=C_FOLLOW_ONLY, label="Thread – neutral majority"),
    mpatches.Patch(color=C_EDGE_SHARED, label="Shared agent(s) between threads"),
    mpatches.Patch(color=C_EDGE_CROSS,  label="Follow relationship across threads"),
]


# ─────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────

def load_network(output_dir: Path) -> pd.DataFrame:
    path = output_dir / "network.csv"
    if not path.exists():
        raise FileNotFoundError(f"network.csv not found in {output_dir}")
    return pd.read_csv(path, dtype=str)


def load_profiles(output_dir: Path) -> pd.DataFrame:
    path = output_dir / "public_profiles.csv"
    if not path.exists():
        raise FileNotFoundError(f"public_profiles.csv not found in {output_dir}")
    return pd.read_csv(path, dtype={"value": float, "agent": str, "attribute": str})


def discover_threads(thread_dir: Path) -> list[str]:
    """
    Find thread IDs from agent_probs_<thread_id>.csv files inside
    the news_sources_corr sub-directory.
    """
    ids = sorted({
        f.stem.replace("agent_probs_", "")
        for f in thread_dir.glob("agent_probs_*.csv")
    })
    return ids


def load_thread_data(thread_dir: Path, thread_id: str) -> dict:
    """Load agent_probs and messages CSVs for one thread."""
    probs_path = thread_dir / f"agent_probs_{thread_id}.csv"
    msgs_path  = thread_dir / f"messages_{thread_id}.csv"

    probs_df = pd.read_csv(probs_path, dtype=str)
    msgs_df  = pd.read_csv(msgs_path,  dtype=str) if msgs_path.exists() else pd.DataFrame()

    initiators = set(probs_df.loc[probs_df["state"] == "infected", "agent"])
    all_agents  = set(probs_df["agent"])
    msg_authors = set(msgs_df["author"].dropna()) if "author" in msgs_df.columns else set()

    return {
        "thread_id":   thread_id,
        "probs_df":    probs_df,
        "msgs_df":     msgs_df,
        "initiators":  initiators,
        "all_agents":  all_agents,
        "msg_authors": msg_authors,
    }


# ─────────────────────────────────────────────────────────────
# Graph construction
# ─────────────────────────────────────────────────────────────

def build_thread_graph(
    thread_data: dict,
    network_df:  pd.DataFrame,
    profiles_df: pd.DataFrame,
) -> dict:
    """
    Build a directed follow-graph for one thread.

    Node classification:
      Initiator   – state == 'infected'
      Reactor     – agent is a message author (but not the initiator)
      Follow-only – in network edges but not a message author
      Floating    – in agent_probs but has no follow edges at all
    """
    thread_id   = thread_data["thread_id"]
    initiators  = thread_data["initiators"]
    all_agents  = thread_data["all_agents"]
    msg_authors = thread_data["msg_authors"]

    # Identify initiator (there should be exactly one per thread)
    initiator = next(iter(initiators)) if initiators else None

    # Build directed graph from the global network, restricted to this thread's agents
    G = nx.DiGraph()
    G.add_nodes_from(all_agents)

    follow_agents: set[str] = set()
    for _, row in network_df.iterrows():
        src, tgt = str(row["from"]), str(row["to"])
        if src in all_agents or tgt in all_agents:
            G.add_node(src)
            G.add_node(tgt)
            G.add_edge(src, tgt)
            follow_agents.add(src)
            follow_agents.add(tgt)

    # Nodes with no edges at all
    floating = {n for n in G.nodes() if G.degree(n) == 0 and n not in {initiator}}

    # Reactors = message authors who are not the initiator
    reactors = (msg_authors - initiators) & all_agents

    # ── Susceptible set ──────────────────────────────────────────────────────
    # An agent is susceptible if it has a directed path TO the initiator in the
    # follow graph (the rumour can propagate along follow edges to reach them).
    susceptible: set[str] = set()
    if initiator and initiator in G:
        for n in G.nodes():
            if n == initiator or n in floating:
                continue
            try:
                if nx.has_path(G, n, initiator):
                    susceptible.add(n)
            except nx.NetworkXError:
                pass

    # Per-node colour & size
    colour_map: dict[str, str] = {}
    size_map:   dict[str, int] = {}
    for n in G.nodes():
        if n == initiator:
            colour_map[n] = C_INITIATOR
            size_map[n]   = 700
        elif n in floating:
            colour_map[n] = C_FLOATING
            size_map[n]   = 350
        elif n in reactors:
            colour_map[n] = C_REACTOR
            size_map[n]   = 440
        else:
            colour_map[n] = C_FOLLOW_ONLY
            size_map[n]   = 260

    # pusr lookup
    pusr_lookup = (
        profiles_df[profiles_df["attribute"] == "pusr"]
        .set_index("agent")["value"]
        .to_dict()
    )

    return {
        "thread_id":   thread_id,
        "initiator":   initiator,
        "reactors":    reactors,
        "floating":    floating,
        "susceptible": susceptible,
        "follow_agents": follow_agents,
        "graph":       G,
        "colour_map":  colour_map,
        "size_map":    size_map,
        "pusr_lookup": pusr_lookup,
        "all_agents":  set(G.nodes()),
    }


# ─────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────

def _spring_pos(G: nx.DiGraph, floating: set[str]) -> dict:
    """Spring layout for connected nodes; evenly-spaced outer ring for floating."""
    connected = [n for n in G.nodes() if n not in floating]
    float_lst = [n for n in G.nodes() if n in floating]

    pos: dict = {}
    if connected:
        H = G.subgraph(connected)
        try:
            pos.update(nx.spring_layout(H, k=2.5, seed=42, iterations=80))
        except Exception:
            pos.update(nx.random_layout(H, seed=42))

    n_float = len(float_lst)
    if n_float:
        radius = 3.5
        for i, n in enumerate(float_lst):
            angle  = 2 * math.pi * i / n_float
            pos[n] = (radius * math.cos(angle), radius * math.sin(angle))

    return pos


def _short_label(agent: str) -> str:
    """Shorten 'convai_agent_123' → 'a_123' for readability."""
    return agent.replace("convai_agent_", "a_")


def draw_thread_full(meta: dict, ax: plt.Axes) -> None:
    G          = meta["graph"]
    floating   = meta["floating"]
    initiator  = meta["initiator"]
    tid        = meta["thread_id"]

    if G.number_of_nodes() == 0:
        ax.text(0.5, 0.5, "No agents found", ha="center", va="center",
                transform=ax.transAxes, fontsize=12)
        ax.set_title(f"Thread {tid} – no data")
        ax.axis("off")
        return

    pos         = _spring_pos(G, floating)
    node_list   = list(G.nodes())
    node_colors = [meta["colour_map"].get(n, C_FOLLOW_ONLY) for n in node_list]
    node_sizes  = [meta["size_map"].get(n, 260)              for n in node_list]

    nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=node_list,
                           node_color=node_colors, node_size=node_sizes, alpha=0.92)
    nx.draw_networkx_edges(G, pos, ax=ax,
                           edge_color=C_EDGE_FOLLOW,
                           arrows=True, arrowsize=14,
                           width=0.8, alpha=0.55,
                           connectionstyle="arc3,rad=0.08",
                           min_source_margin=10, min_target_margin=10)

    labels = {n: _short_label(n) for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=5.5)

    follow_only_count = len(
        meta["follow_agents"] - meta["reactors"] - ({initiator} if initiator else set())
    )
    stats = (
        f"Total agents: {G.number_of_nodes()}  |  "
        f"Follow edges: {G.number_of_edges()}  |  "
        f"Reactors: {len(meta['reactors'])}  |  "
        f"Follow-only: {follow_only_count}  |  "
        f"Floating: {len(floating)}  |  "
        f"Susceptible: {len(meta['susceptible'])}"
    )
    ax.set_title(
        f"Thread {tid}\n[INITIATOR: {_short_label(initiator) if initiator else 'none'}]\n{stats}",
        fontsize=8, pad=10,
    )
    ax.axis("off")


def draw_thread_susceptible(meta: dict, ax: plt.Axes) -> None:
    G           = meta["graph"]
    initiator   = meta["initiator"]
    susceptible = meta["susceptible"]
    reactors    = meta["reactors"]
    tid         = meta["thread_id"]

    keep = susceptible | ({initiator} if initiator else set())
    S    = G.subgraph(keep).copy()

    if S.number_of_nodes() == 0 or not initiator:
        ax.text(
            0.5, 0.5,
            "No susceptible agents found\n"
            "(no follow-edge path leads to the initiator)",
            ha="center", va="center", transform=ax.transAxes,
            fontsize=11, color="#666666",
        )
        ax.set_title(f"Thread {tid} – Susceptible subgraph (empty)", fontsize=8)
        ax.axis("off")
        return

    try:
        pos = nx.spring_layout(S, k=2.5, seed=42, iterations=80)
    except Exception:
        pos = nx.random_layout(S, seed=42)

    node_colors, node_sizes = [], []
    for n in S.nodes():
        if n == initiator:
            node_colors.append(C_INITIATOR)
            node_sizes.append(700)
        elif n in reactors:
            node_colors.append(C_SUSC_REACTOR)
            node_sizes.append(440)
        else:
            node_colors.append(C_SUSC_FOLLOW)
            node_sizes.append(260)

    nx.draw_networkx_nodes(S, pos, ax=ax,
                           node_color=node_colors, node_size=node_sizes, alpha=0.92)
    nx.draw_networkx_edges(S, pos, ax=ax,
                           edge_color=C_EDGE_FOLLOW,
                           arrows=True, arrowsize=14,
                           width=0.8, alpha=0.55,
                           connectionstyle="arc3,rad=0.08",
                           min_source_margin=10, min_target_margin=10)

    labels = {n: _short_label(n) for n in S.nodes()}
    nx.draw_networkx_labels(S, pos, labels=labels, ax=ax, font_size=5.5)

    n_susc_reactors = len(susceptible & reactors)
    n_susc_follow   = len(susceptible - reactors)
    stats = (
        f"Susceptible agents: {len(susceptible)}  |  "
        f"of which reactors: {n_susc_reactors}  |  "
        f"follow-only: {n_susc_follow}  |  "
        f"Edges in subgraph: {S.number_of_edges()}"
    )
    ax.set_title(
        f"Thread {tid} – Susceptible subgraph\n"
        f"[INITIATOR: {_short_label(initiator)}]\n{stats}",
        fontsize=8, pad=10,
    )
    ax.axis("off")


def save_thread_pdf(meta: dict, output_dir: Path) -> Path:
    tid      = meta["thread_id"]
    initiator = meta["initiator"]
    footer = (
        f"CoNVaI / PHEME Ottawa Shooting  |  Thread {tid}  "
        f"|  Initiator: {_short_label(initiator) if initiator else 'none'}"
    )
    pdf_path = output_dir / f"{tid}.pdf"
    with PdfPages(pdf_path) as pdf:
        # Page 1 – full graph
        fig, ax = plt.subplots(figsize=(15, 11))
        draw_thread_full(meta, ax)
        ax.legend(handles=LEGEND_THREAD, loc="lower left",
                  fontsize=7.5, framealpha=0.85)
        fig.text(0.5, 0.005, footer, ha="center", fontsize=7, color="#666666")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page 2 – susceptible subgraph
        fig, ax = plt.subplots(figsize=(15, 11))
        draw_thread_susceptible(meta, ax)
        ax.legend(handles=LEGEND_SUSCEPTIBLE, loc="lower left",
                  fontsize=7.5, framealpha=0.85)
        fig.text(0.5, 0.005,
                 footer + "  |  PAGE 2: Susceptible subgraph",
                 ha="center", fontsize=7, color="#666666")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    return pdf_path


# ─────────────────────────────────────────────────────────────
# Cross-thread graph
# ─────────────────────────────────────────────────────────────

def build_cross_thread_edges(all_metas: list[dict]) -> dict:
    """
    Mirror of pheme_graphs.py build_cross_thread_edges.
    shared: frozenset pairs that share >= 1 agent
    follow: directed pairs where thread A follows thread B (no shared agents)
    """
    meta_map = {m["thread_id"]: m for m in all_metas}
    follow_sources = {
        tid: {e[0] for e in m["graph"].edges()}
        for tid, m in meta_map.items()
    }

    shared_pairs: set[frozenset] = set()
    follow_pairs: list[tuple]    = []

    tids = [m["thread_id"] for m in all_metas]
    for i, tid_a in enumerate(tids):
        agents_a = meta_map[tid_a]["all_agents"]
        from_a   = follow_sources[tid_a]
        for j, tid_b in enumerate(tids):
            if i == j:
                continue
            agents_b = meta_map[tid_b]["all_agents"]
            pair     = frozenset({tid_a, tid_b})
            if agents_a & agents_b:
                shared_pairs.add(pair)
            elif pair not in shared_pairs and from_a & agents_b:
                follow_pairs.append((tid_a, tid_b))

    follow_pairs = [
        (a, b) for a, b in follow_pairs
        if frozenset({a, b}) not in shared_pairs
    ]
    return {"shared": list(shared_pairs), "follow": follow_pairs}


def draw_global_graph(all_metas: list[dict], output_dir: Path) -> Path:
    cross_edges = build_cross_thread_edges(all_metas)

    # Build layout graph
    G_layout = nx.Graph()
    G_layout.add_nodes_from(m["thread_id"] for m in all_metas)
    for pair in cross_edges["shared"]:
        a, b = tuple(pair)
        G_layout.add_edge(a, b)
    for a, b in cross_edges["follow"]:
        if not G_layout.has_edge(a, b):
            G_layout.add_edge(a, b)

    try:
        pos = nx.kamada_kawai_layout(G_layout)
    except Exception:
        try:
            pos = nx.spring_layout(G_layout, k=4.0, seed=42, iterations=120)
        except Exception:
            pos = nx.random_layout(G_layout, seed=42)

    meta_map = {m["thread_id"]: m for m in all_metas}
    all_tids = set(meta_map.keys())

    # Node colours: gold if has initiator, blue otherwise
    node_colours, node_sizes, node_labels = [], [], {}
    for tid in all_tids:
        m = meta_map[tid]
        has_initiator = bool(m.get("initiator"))
        node_colours.append(C_INITIATOR if has_initiator else C_FOLLOW_ONLY)
        n_agents = len(m["all_agents"])
        node_sizes.append(max(600, 300 + 20 * n_agents))
        short = str(tid)[-12:]
        node_labels[tid] = (
            f"…{short}\n({n_agents} agents)\n"
            f"susc={len(m['susceptible'])}"
        )

    vis_pos = {tid: pos[tid] for tid in all_tids if tid in pos}

    # Build display graph
    NG = nx.Graph()
    NG.add_nodes_from(all_tids)

    shared_el = [tuple(pair) for pair in cross_edges["shared"] if pair <= all_tids]
    shared_covered = {frozenset(p) for p in shared_el}
    follow_el = [
        (a, b) for a, b in cross_edges["follow"]
        if a in all_tids and b in all_tids
        and frozenset({a, b}) not in shared_covered
    ]

    footer = (
        "Node size ∝ agents in thread  |  Gold = has initiator  "
        "|  Label shows thread ID suffix  |  "
        "━ shared agents (undirected)   → follow-only (directed)"
    )

    pdf_path = output_dir / "all.pdf"
    with PdfPages(pdf_path) as pdf:
        fig, ax = plt.subplots(figsize=(22, 17))

        nx.draw_networkx_nodes(
            NG, vis_pos, ax=ax,
            nodelist=list(all_tids),
            node_color=node_colours,
            node_size=node_sizes,
            alpha=0.93,
        )
        nx.draw_networkx_labels(
            NG, vis_pos,
            labels=node_labels, ax=ax, font_size=8,
        )

        if shared_el:
            UG = nx.Graph()
            UG.add_nodes_from(all_tids)
            UG.add_edges_from(shared_el)
            nx.draw_networkx_edges(
                UG, vis_pos, edgelist=shared_el, ax=ax,
                edge_color=C_EDGE_SHARED,
                arrows=False, width=2.5, alpha=0.75,
            )

        if follow_el:
            DG = nx.DiGraph()
            DG.add_nodes_from(all_tids)
            DG.add_edges_from(follow_el)
            nx.draw_networkx_edges(
                DG, vis_pos, edgelist=follow_el, ax=ax,
                edge_color=C_EDGE_CROSS,
                arrows=True, arrowsize=20,
                width=1.2, alpha=0.60,
                connectionstyle="arc3,rad=0.12",
                min_source_margin=16, min_target_margin=16,
            )

        total_susc = sum(len(m["susceptible"]) for m in all_metas)
        ax.set_title(
            f"CoNVaI – Ottawa Shooting: All {len(all_tids)} Threads\n"
            f"Threads: {len(all_tids)}  |  "
            f"Total susceptible agents (sum): {total_susc}  |  "
            f"Shared-agent edges: {len(shared_el)}  |  "
            f"Follow edges: {len(follow_el)}",
            fontsize=11, pad=14,
        )
        ax.legend(handles=LEGEND_GLOBAL, loc="upper left",
                  fontsize=9, framealpha=0.88)
        ax.axis("off")
        fig.text(0.5, 0.003, footer, ha="center",
                 fontsize=8, color="#666666")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    print(f"  Global graph -> {pdf_path}")
    return pdf_path


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate PDF graphs from CoNVaI CSV outputs."
    )
    parser.add_argument(
        "--output_dir", default="./convai_outputs",
        help="Directory containing CoNVaI CSV outputs (default: ./convai_outputs).",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    thread_dir = output_dir / "news_sources_corr"

    for path, label in [
        (output_dir,  "output_dir"),
        (thread_dir,  "news_sources_corr"),
        (output_dir / "network.csv",         "network.csv"),
        (output_dir / "public_profiles.csv", "public_profiles.csv"),
    ]:
        if not path.exists():
            print(f"[ERROR] {label} not found: {path}", file=sys.stderr)
            sys.exit(1)

    graphs_dir = output_dir / "graphs_output"
    graphs_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output dir : {graphs_dir}\n")

    # Load global files
    print("[INFO] Loading network.csv ...")
    network_df = load_network(output_dir)
    print(f"       {len(network_df):,} edges")

    print("[INFO] Loading public_profiles.csv ...")
    profiles_df = load_profiles(output_dir)
    print(f"       {len(profiles_df):,} profile rows")

    # Discover threads
    thread_ids = discover_threads(thread_dir)
    if not thread_ids:
        print("[ERROR] No agent_probs_*.csv files found in", thread_dir, file=sys.stderr)
        sys.exit(1)
    print(f"[INFO] Found {len(thread_ids)} thread(s): {thread_ids}\n")

    # Build and draw per-thread graphs
    all_metas = []
    for idx, tid in enumerate(thread_ids, 1):
        print(f"[{idx}/{len(thread_ids)}] Thread {tid}")
        thread_data = load_thread_data(thread_dir, tid)
        meta        = build_thread_graph(thread_data, network_df, profiles_df)
        all_metas.append(meta)

        pdf = save_thread_pdf(meta, graphs_dir)
        G   = meta["graph"]
        print(
            f"         agents={G.number_of_nodes():4d}  "
            f"edges={G.number_of_edges():5d}  "
            f"reactors={len(meta['reactors']):3d}  "
            f"floating={len(meta['floating']):3d}  "
            f"susceptible={len(meta['susceptible']):4d}  "
            f"-> {pdf.name}"
        )

    # Cross-thread global graph
    print(f"\n[INFO] Building cross-thread graph ({len(all_metas)} threads) ...")
    draw_global_graph(all_metas, graphs_dir)

    print(f"\n[DONE] {len(all_metas) + 1} PDF(s) saved to:\n   {graphs_dir.resolve()}")
    pdfs = list(graphs_dir.glob("*.pdf"))
    for p in sorted(pdfs):
        print(f"   {p.name}")


if __name__ == "__main__":
    main()
