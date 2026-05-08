#!/usr/bin/env python3
"""
generate_sim_folders.py

For each agent_probs_<thread>_<config>.csv found in
datasets/convai-selected/news_sources_corr/, this script:

  1. Identifies the source thread folder under convai/600/<thread>/
  2. Creates convai/600/<thread>_<config>/
  3. Copies all contents of convai/600/<thread>/ into that new folder
  4. Patches the copied default_mas.mas2j with the agent parameters from the CSV

Files named agent_probs_<thread>.csv (no config suffix) are ignored.

Usage:
    python generate_sim_folders.py [--dry-run] [--base-dir PATH]
"""

import argparse
import csv
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def parse_agent_probs(csv_path: Path) -> dict:
    """Return {agent_name: {pinf, pmd, pad, popi, prd, state}} from a CSV."""
    agents = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row["agent"].strip()
            agents[name] = {
                "pinf":  row["pinf"].strip(),
                "pmd":   row["pmd"].strip(),
                "pad":   row["pad"].strip(),
                "popi":  row["popi"].strip(),
                "prd":   row["prd"].strip(),
                "state": row["state"].strip(),
            }
    return agents


# ---------------------------------------------------------------------------
# .mas2j patching
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
# Main
# ---------------------------------------------------------------------------

def generate_folders(base_dir: Path, dry_run: bool = False) -> None:
    convai_600  = base_dir / "convai" / "600"
    dataset_dir = base_dir / "datasets" / "convai-selected" / "news_sources_corr"

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
        thread_dir = convai_600 / thread_id
        dest_dir   = convai_600 / f"{thread_id}_{config_name}"

        print(f"  CSV  : {csv_path.relative_to(base_dir)}")
        print(f"  SRC  : {thread_dir.relative_to(base_dir)}")
        print(f"  DEST : {dest_dir.relative_to(base_dir)}")

        if not thread_dir.exists():
            print(f"  [WARN] source thread folder not found – skipping.\n")
            continue

        # 1. Copy thread folder contents into dest_dir
        if dry_run:
            print(f"  [dry] would copy {thread_dir} -> {dest_dir}")
        else:
            if dest_dir.exists():
                print(f"  [info] destination exists – removing and re-creating.")
                shutil.rmtree(dest_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            for item in thread_dir.iterdir():
                if item.is_dir():
                    shutil.copytree(item, dest_dir / item.name)
                else:
                    shutil.copy2(item, dest_dir / item.name)

        # 2. Parse CSV
        agents = parse_agent_probs(csv_path)
        print(f"  Loaded {len(agents)} agent record(s) from CSV.")

        # 3. Patch copied .mas2j
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

        print()

    print("Done.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
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
