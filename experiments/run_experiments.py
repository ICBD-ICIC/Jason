#!/usr/bin/env python3
import csv
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# --- Configuration ---
MAS_FILE = Path("simulating_social_media_non_partisan.mas2j")
AGT_DIR = Path("src/agt")
CSV_DIR = Path(MAS_FILE.stem)  # folder with CSV files
RESULTS_DIR = Path("results") / MAS_FILE.stem  # results/<mas_name>
LOG_FILE = "mas.log"

GOOD_DIR = RESULTS_DIR / "good"
DISCARD_DIR = RESULTS_DIR / "discard"
GOOD_DIR.mkdir(parents=True, exist_ok=True)
DISCARD_DIR.mkdir(parents=True, exist_ok=True)

# --- Helper functions ---
def backup_agents(agent_count):
    backups = []
    for i in range(agent_count):
        agent_file = AGT_DIR / f"agent{i}.asl"
        backup_file = agent_file.with_suffix(".asl.bak")
        shutil.copy(agent_file, backup_file)
        backups.append((agent_file, backup_file))
    return backups

def restore_agents(backups):
    for agent_file, backup_file in backups:
        shutil.move(backup_file, agent_file)

def update_agents(rows):
    for i, row in enumerate(rows):
        agent_file = AGT_DIR / f"agent{i}.asl"
        political_standpoint, is_observer, demographics, persona_description = row

        # Escape double quotes
        demographics = demographics.replace('"', '\\"')
        persona_description = persona_description.replace('"', '\\"')

        content = agent_file.read_text(encoding='utf-8')
        content = content.replace('political_standpoint(ps_placeholder)', f'political_standpoint("{political_standpoint}")')
        content = content.replace('demographics(d_placeholder)', f'demographics("{demographics}")')
        content = content.replace('persona_description(pd_placeholder)', f'persona_description("{persona_description}")')
        agent_file.write_text(content, encoding='utf-8')

def run_mas(mas_file):
    return subprocess.run(["gradle", "clean", "run", f"-PmasFile={mas_file}"], shell=True, check=True)
    
def read_csv_rows(csv_file):
    """Read CSV safely and return rows (skip header)."""
    rows = []
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            rows.append(row)
    return rows

def process_csv(csv_file):
    print(f"Processing CSV: {csv_file.name}")
    rows = read_csv_rows(csv_file)
    agent_count = len(rows)

    success = False
    while not success:
        backups = backup_agents(agent_count)
        update_agents(rows)
        run_mas(MAS_FILE)

        log_path = Path(LOG_FILE)
        if not log_path.exists():
            print(f"Warning: {LOG_FILE} not found. Retrying...")
            restore_agents(backups)
            continue

        with open(log_path, encoding='utf-8') as f:
            count_agent10 = sum(1 for line in f if line.startswith("[agent10]"))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        if count_agent10 <= 1:
            dest = DISCARD_DIR
            print("Log discarded (0 or 1 [agent10] occurrence). Retrying...")
        else:
            dest = GOOD_DIR
            print("Log accepted as good run.")
            success = True

        dest_file = dest / f"{csv_file.stem}_{timestamp}.log"
        shutil.move(LOG_FILE, dest_file)
        print(f"Saved to {dest_file}")

        restore_agents(backups)
        print("-" * 40)

# --- Main workflow ---
def main():
    for csv_file in CSV_DIR.glob("agent_config_*.csv"):
        process_csv(csv_file)
    print("All experiments completed.")

if __name__ == "__main__":
    main()
