#!/usr/bin/env python3
"""
generate_sim_folders.py

For each agent_probs_<thread>_<config>.csv found in
datasets/convai-selected/news_sources_corr/, this script:

  1. Identifies the source thread folder under convai/600/<thread>/
  2. Creates convai/600/<thread>_<config>/
  3. Copies all contents of convai/600/<thread>/ into that new folder
  4. Patches the copied default_mas.mas2j with the agent parameters from the CSV

  Additionally, for each agent_probs_raw_<thread>.csv found alongside the
  agent_probs CSVs, this script:

  5. Identifies the source thread folder under convai/600_llm/<thread>/
  6. Creates convai/600_llm/<thread>_<config>/
  7. Copies all contents of convai/600/<thread>/ into that new folder
     (using the numeric-param variant as the base, same as the sampler does)
  8. Patches the copied default_mas.mas2j with natural-language personality
     descriptions derived from the numeric params, mirroring the
     make_agent_probs_raw / make_personality_description logic from
     generate_convai_inputs_sampled.py

Files named agent_probs_<thread>.csv (no config suffix) are ignored.

Usage:
    python generate_sim_folders.py [--dry-run] [--base-dir PATH]
"""

import argparse
import csv
import math
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def parse_agent_probs(csv_path: Path) -> dict:
    """Return {agent_name: {pinf, pmd, pad, popi, prd, state, susceptible}}
    from an agent_probs_<thread>_<config>.csv file."""
    agents = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row["agent"].strip()
            agents[name] = {
                "pinf":        row["pinf"].strip(),
                "pmd":         row["pmd"].strip(),
                "pad":         row["pad"].strip(),
                "popi":        row["popi"].strip(),
                "prd":         row["prd"].strip(),
                "state":       row["state"].strip(),
                "susceptible": row.get("susceptible", "true").strip(),
            }
    return agents


# ---------------------------------------------------------------------------
# Natural-language personality description
# (mirrors generate_convai_inputs_sampled.make_personality_description)
# ---------------------------------------------------------------------------

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

    Mirrors generate_convai_inputs_sampled.make_personality_description exactly.
    """
    pinf_level = _level(pinf, 0.05, 0.15)
    pinf_phrases = {
        "low":      "You are highly resistant to new claims and rarely change your mind based on a single encounter.",
        "moderate": "You are somewhat open to new information, but a single message is not enough to fully convince you.",
        "high":     "You are quite impressionable and can be convinced by a compelling message on first contact.",
    }

    pmd_level = _level(pmd, 0.05, 0.10)
    pmd_phrases = {
        "low":      "You do not tend to develop scepticism readily - exposure to a claim does not typically make you dismissive of it.",
        "moderate": "You sometimes develop a critical distance from claims you encounter, becoming harder to persuade thereafter.",
        "high":     "You are quick to become sceptical: once you encounter a claim and resist it, you actively discount it going forward.",
    }

    pad_level = _level(pad, 0.05, 0.15)
    pad_phrases = {
        "low":      "When you disagree with a message, you almost never change your position - you hold your ground firmly.",
        "moderate": "Encountering disagreement occasionally causes you to reconsider and adjust your stance.",
        "high":     "You are sensitive to opposing views: disagreement with a message can lead you to adopt the other side's position.",
    }

    popi_level = _level(popi, 0.10, 0.25)
    popi_phrases = {
        "low":      "Agreement with a message does not particularly strengthen your existing beliefs.",
        "moderate": "When you agree with a message or successfully resist a challenge, your convictions are moderately reinforced.",
        "high":     "Confirmation of your views or resisting a contrary message significantly deepens your commitment to your current position.",
    }

    prd_level = _level(prd, 0.10, 0.40)
    prd_phrases = {
        "low":      "You read and process incoming messages slowly, engaging with only a small fraction of what reaches you.",
        "moderate": "You read messages at an average pace, engaging with a reasonable share of the information flow.",
        "high":     "You are a highly active reader who processes a large proportion of incoming messages quickly.",
    }

    return (
        f"{pinf_phrases[pinf_level]} "
        f"{pmd_phrases[pmd_level]} "
        f"{pad_phrases[pad_level]} "
        f"{popi_phrases[popi_level]} "
        f"{prd_phrases[prd_level]}"
    )


def agents_to_raw(agents: dict) -> dict:
    """
    Convert a numeric-param agent dict (from parse_agent_probs) into the
    natural-language form used by the LLM variant.

    Returns {llm_agent_name: {personality_description, state, susceptible}}.
    The agent name is translated from convai_agent_N -> convai_llm_agent_N.
    """
    raw = {}
    for name, params in agents.items():
        llm_name = name.replace("convai_agent_", "convai_llm_agent_")
        raw[llm_name] = {
            "personality_description": make_personality_description(
                pinf=float(params["pinf"]),
                pmd=float(params["pmd"]),
                pad=float(params["pad"]),
                popi=float(params["popi"]),
                prd=float(params["prd"]),
            ),
            "state":       params["state"],
            "susceptible": params["susceptible"],
        }
    return raw


# ---------------------------------------------------------------------------
# .mas2j patching — numeric variant (convai/600)
# ---------------------------------------------------------------------------

AGENT_BLOCK_RE = re.compile(
    r'(?P<indent>[ \t]*)(?P<name>convai_agent_\d+)'
    r'(?P<mid>[ \t]+convai_agent\s*\[[ \t]*beliefs=")'
    r'agent\((?P=name)\)'
    r',[ \t]*pinf\([^)]*\)'
    r',[ \t]*pmd\([^)]*\)'
    r',[ \t]*pad\([^)]*\)'
    r',[ \t]*popi\([^)]*\)'
    r',[ \t]*prd\([^)]*\)'
    r',[ \t]*state\([^)]*\)'
    r'(?P<tail>"[^\]]*\].*?)(?=\n)',
    re.DOTALL,
)


def patch_mas2j(mas2j_text: str, agents: dict) -> str:
    """Patch numeric-param beliefs into a convai/600 .mas2j file."""
    def replacer(m: re.Match) -> str:
        name = m.group("name")
        if name not in agents:
            return m.group(0)
        p = agents[name]
        beliefs = (
            f'agent({name}), '
            f'pinf({p["pinf"]}), '
            f'pmd({p["pmd"]}), '
            f'pad({p["pad"]}), '
            f'popi({p["popi"]}), '
            f'prd({p["prd"]}), '
            f'state({p["state"]})'
        )
        return (
            f'{m.group("indent")}{name}'
            f'{m.group("mid")}{beliefs}'
            f'{m.group("tail")}'
        )

    return AGENT_BLOCK_RE.sub(replacer, mas2j_text)


# ---------------------------------------------------------------------------
# .mas2j patching — natural-language variant (convai/600_llm)
# ---------------------------------------------------------------------------

LLM_AGENT_BLOCK_RE = re.compile(
    r'(?P<indent>[ \t]*)(?P<name>convai_llm_agent_\d+)'
    r'(?P<mid>[ \t]+convai_llm_agent\s*\[[ \t]*beliefs=")'
    r'agent\((?P=name)\)'
    r',[ \t]*personality_description\([^)]*\)'
    r',[ \t]*state\([^)]*\)'
    r'(?P<tail>"[^\]]*\].*?)(?=\n)',
    re.DOTALL,
)


def patch_mas2j_llm(mas2j_text: str, raw_agents: dict) -> str:
    """
    Patch natural-language personality beliefs into a convai/600_llm .mas2j file.

    Expects raw_agents keyed by convai_llm_agent_N with keys:
        personality_description, state, susceptible.
    """
    def replacer(m: re.Match) -> str:
        name = m.group("name")
        if name not in raw_agents:
            return m.group(0)
        p = raw_agents[name]
        # Escape any double-quotes inside the description so the .mas2j stays valid
        desc = p["personality_description"].replace('"', '\\"')
        beliefs = (
            f'agent({name}), '
            f'personality_description("{desc}"), '
            f'state({p["state"]})'
        )
        return (
            f'{m.group("indent")}{name}'
            f'{m.group("mid")}{beliefs}'
            f'{m.group("tail")}'
        )

    return LLM_AGENT_BLOCK_RE.sub(replacer, mas2j_text)


# ---------------------------------------------------------------------------
# CSV discovery  —  agent_probs_<thread>_<config>.csv only
# ---------------------------------------------------------------------------

CSV_PATTERN = re.compile(r'^agent_probs_(?P<thread>\d+)_(?P<config>.+)\.csv$')


def discover_csv_files(dataset_dir: Path) -> list[tuple[str, str, Path]]:
    """Return [(thread_id, config_name, csv_path), ...], skipping bare thread files."""
    results = []
    for csv_path in sorted(dataset_dir.glob("**/*.csv")):
        m = CSV_PATTERN.match(csv_path.name)
        if not m:
            print(f"  [skip] {csv_path.name}")
            continue
        results.append((m.group("thread"), m.group("config"), csv_path))
    return results


# ---------------------------------------------------------------------------
# Shared helper: copy a source folder into dest_dir
# ---------------------------------------------------------------------------

def copy_thread_folder(src: Path, dest: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry] would copy {src} -> {dest}")
        return
    if dest.exists():
        print(f"  [info] destination exists – removing and re-creating.")
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_dir():
            shutil.copytree(item, dest / item.name)
        else:
            shutil.copy2(item, dest / item.name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_folders(base_dir: Path, dry_run: bool = False) -> None:
    convai_600     = base_dir / "convai" / "600"
    convai_600_llm = base_dir / "convai" / "600_llm"
    dataset_dir    = base_dir / "datasets" / "convai-selected" / "news_sources_corr"

    if not convai_600.exists():
        sys.exit(f"ERROR: {convai_600} does not exist.")
    if not dataset_dir.exists():
        sys.exit(f"ERROR: {dataset_dir} does not exist.")

    csv_entries = discover_csv_files(dataset_dir)
    if not csv_entries:
        print("No agent_probs_<thread>_<config>.csv files found – nothing to do.")
        return

    print(f"Found {len(csv_entries)} CSV file(s) to process.\n")

    mas_filename = "default_mas.mas2j"

    for thread_id, config_name, csv_path in csv_entries:
        thread_dir     = convai_600     / thread_id
        dest_dir       = convai_600     / f"{thread_id}_{config_name}"
        llm_thread_dir = convai_600_llm / thread_id
        llm_dest_dir   = convai_600_llm / f"{thread_id}_{config_name}"

        print(f"  CSV  : {csv_path.relative_to(base_dir)}")

        # ------------------------------------------------------------------ #
        # 1.  convai/600/<thread>_<config>  — numeric variant                #
        # ------------------------------------------------------------------ #
        print(f"\n  [600] SRC  : {thread_dir.relative_to(base_dir)}")
        print(f"  [600] DEST : {dest_dir.relative_to(base_dir)}")

        if not thread_dir.exists():
            print(f"  [WARN] convai/600/{thread_id}/ not found – skipping numeric variant.\n")
        else:
            copy_thread_folder(thread_dir, dest_dir, dry_run)

            agents = parse_agent_probs(csv_path)
            print(f"  Loaded {len(agents)} agent record(s) from CSV.")

            mas2j_dest = dest_dir / mas_filename
            if dry_run:
                if (thread_dir / mas_filename).exists():
                    print(f"  [dry] would patch {mas_filename} with {len(agents)} agents.")
                else:
                    print(f"  [WARN] {mas_filename} not found in source – skip patch.")
            else:
                if not mas2j_dest.exists():
                    print(f"  [WARN] {mas_filename} not found in {dest_dir} – skip patch.")
                else:
                    original = mas2j_dest.read_text(encoding="utf-8")
                    patched  = patch_mas2j(original, agents)
                    mas2j_dest.write_text(patched, encoding="utf-8")
                    changed = sum(1 for name in agents if f"agent({name})" in patched)
                    print(f"  Patched {changed} agent entries in {mas_filename}.")

        # ------------------------------------------------------------------ #
        # 2.  convai/600_llm/<thread>_<config>  — natural-language variant   #
        #                                                                     #
        # Base folder: convai/600/<thread>/ (same numeric base as the        #
        # sampler uses — generate_convai_inputs_sampled uses the numeric      #
        # probs CSV to derive the raw/NL form, not a separate LLM base).     #
        # If convai/600_llm/<thread>/ exists it is used preferentially as    #
        # the base (it may carry LLM-specific agent files / config).         #
        # ------------------------------------------------------------------ #
        llm_base = llm_thread_dir if llm_thread_dir.exists() else thread_dir

        print(f"\n  [600_llm] BASE : {llm_base.relative_to(base_dir)}")
        print(f"  [600_llm] DEST : {llm_dest_dir.relative_to(base_dir)}")

        if not llm_base.exists():
            print(f"  [WARN] neither convai/600_llm/{thread_id}/ nor convai/600/{thread_id}/ "
                  f"found – skipping LLM variant.\n")
        else:
            copy_thread_folder(llm_base, llm_dest_dir, dry_run)

            # Derive natural-language beliefs from the same numeric CSV
            if not dry_run or True:   # always compute so dry-run can report counts
                agents     = parse_agent_probs(csv_path)
                raw_agents = agents_to_raw(agents)

            print(f"  Derived NL descriptions for {len(raw_agents)} LLM agent(s).")

            mas2j_dest_llm = llm_dest_dir / mas_filename
            if dry_run:
                if (llm_base / mas_filename).exists():
                    print(f"  [dry] would patch {mas_filename} with {len(raw_agents)} LLM agents.")
                else:
                    print(f"  [WARN] {mas_filename} not found in LLM base – skip patch.")
            else:
                if not mas2j_dest_llm.exists():
                    print(f"  [WARN] {mas_filename} not found in {llm_dest_dir} – skip patch.")
                else:
                    original = mas2j_dest_llm.read_text(encoding="utf-8")
                    patched  = patch_mas2j_llm(original, raw_agents)
                    mas2j_dest_llm.write_text(patched, encoding="utf-8")
                    changed = sum(
                        1 for name in raw_agents
                        if f"agent({name})" in patched
                    )
                    print(f"  Patched {changed} LLM agent entries in {mas_filename}.")

        print()

    print("Done.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-dir", default=".",
                        help="Project root (default: current directory).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print actions without modifying files.")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    print(f"Base directory : {base_dir}")
    print(f"Dry run        : {args.dry_run}\n")
    generate_folders(base_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()