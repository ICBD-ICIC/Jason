#!/usr/bin/env python3
"""
run_simulations.py
...

taskkill //F //IM java.exe
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
import os
import signal

_current_proc = None

def _kill_current(signum, frame):
    global _current_proc
    if _current_proc and _current_proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(_current_proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sys.exit(1)

signal.signal(signal.SIGINT, _kill_current)
signal.signal(signal.SIGTERM, _kill_current)


# ---------------------------------------------------------------------------
# Simulation folders to run — comment/uncomment as needed
# ---------------------------------------------------------------------------

SIM_FOLDERS = [
    "convai/600/524949443607412737",
    "convai/600_llm/524949443607412737",
]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def stop_gradle_daemons(base_dir: Path) -> None:
    subprocess.call(
        [str((base_dir / "gradlew.bat").resolve()), "--stop"],
        cwd=base_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_gradle(
    sim_folder: str,
    gradle_cmd: str,
    mas_file: str,
    dry_run: bool,
    base_dir: Path,
) -> tuple[bool, str]:
    folder_name = Path(sim_folder).name
    cmd = [
        str((base_dir / "gradlew.bat").resolve()),
        "clean",
        "run",
        f"-PgeneratedFolder={sim_folder}",
        f"-PmasFile={mas_file}",
    ]

    if dry_run:
        print(f"  [dry] cd {base_dir}  &&  {' '.join(cmd)}")
        return True, f"{folder_name}: dry-run"

    print(f"  [RUN] {folder_name}  ->  gradlew.bat clean run "
          f"-PgeneratedFolder={sim_folder} -PmasFile={mas_file}")
    t0 = time.monotonic()

    try:
        global _current_proc
        proc = subprocess.Popen(
            cmd,
            cwd=base_dir,
            text=True,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        _current_proc = proc
        try:
            proc.wait(timeout=10 * 60)
        except subprocess.TimeoutExpired:
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.wait()
            stop_gradle_daemons(base_dir)
            elapsed = time.monotonic() - t0
            return False, f"{folder_name}: TIMEOUT after {elapsed:.1f}s"

        elapsed = time.monotonic() - t0
        success = proc.returncode == 0
        status  = "OK" if success else f"FAILED (rc={proc.returncode})"
        stop_gradle_daemons(base_dir)
        return success, f"{folder_name}: {status}  [{elapsed:.1f}s]"

    except FileNotFoundError:
        return False, f"{folder_name}: ERROR - gradlew.bat not found at {base_dir}."


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_all(
    base_dir: Path,
    gradle_cmd: str,
    mas_file: str,
    dry_run: bool,
    stop_on_error: bool,
) -> None:
    sim_folders = [f for f in SIM_FOLDERS]  # copy so the original is untouched

    if not sim_folders:
        print("No simulation folders defined in SIM_FOLDERS.")
        return

    print(f"Scheduled {len(sim_folders)} simulation folder(s):\n")
    for f in sim_folders:
        print(f"  {f}")
    print()

    results: list[tuple[bool, str]] = []

    for sim_folder in sim_folders:
        ok, msg = run_gradle(sim_folder, gradle_cmd, mas_file, dry_run, base_dir)
        results.append((ok, msg))
        icon = "✓" if ok else "✗"
        print(f"  {icon} {msg}")
        if not ok and stop_on_error:
            print("\nStopping on first error (--stop-on-error).")
            break

    total  = len(results)
    passed = sum(1 for ok, _ in results if ok)
    failed = total - passed
    print(f"\n{'='*50}")
    print(f"Summary: {passed}/{total} succeeded, {failed} failed.")

    if failed:
        print("\nFailed runs:")
        for ok, msg in results:
            if not ok:
                print(f"  ✗ {msg}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-dir",      default=".",
                        help="Project root (default: current directory).")
    parser.add_argument("--gradle",        default="gradle",
                        help="Gradle executable (default: gradle).")
    parser.add_argument("--mas-file",      default="default_mas.mas2j",
                        help=".mas2j filename (default: default_mas.mas2j).")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Print commands without executing them.")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="Stop on first failure.")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    print(f"Base directory : {base_dir}")
    print(f"Gradle command : {args.gradle}")
    print(f"Mas file       : {args.mas_file}")
    print(f"Dry run        : {args.dry_run}")
    print(f"Stop on error  : {args.stop_on_error}\n")

    run_all(
        base_dir      = base_dir,
        gradle_cmd    = args.gradle,
        mas_file      = args.mas_file,
        dry_run       = args.dry_run,
        stop_on_error = args.stop_on_error,
    )


if __name__ == "__main__":
    main()