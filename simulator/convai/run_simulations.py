#!/usr/bin/env python3
"""
run_simulations.py

Runs the Gradle task for every subfolder found directly under convai/600/.

The command executed for each folder is:
    gradle clean run -PgeneratedFolder=convai/600/<folder_name> -PmasFile=default_mas.mas2j

Usage:
    python run_simulations.py [options]

Options:
    --base-dir PATH     Root of the project (default: current working directory).
    --gradle  CMD       Gradle executable (default: gradle). Use ./gradlew for the wrapper.
    --mas-file NAME     Name of the .mas2j file (default: default_mas.mas2j).
    --dry-run           Print commands without executing them.
    --stop-on-error     Abort as soon as one Gradle invocation fails.
"""

"""
Useful commands:
    tasklist | grep -i "java\|gradle"
    taskkill //F //IM java.exe //T
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
# Discovery
# ---------------------------------------------------------------------------

def discover_sim_folders(convai_600: Path) -> list[Path]:
    """Return every immediate subdirectory of convai/600/, sorted."""
    if not convai_600.exists():
        return []
    return sorted(p for p in convai_600.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def stop_gradle_daemons(base_dir: Path) -> None:
    """Send --stop to all running Gradle daemons for this installation."""
    subprocess.call(
        [str((base_dir / "gradlew.bat").resolve()), "--stop"],
        cwd=base_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_gradle(
    sim_dir: Path,
    gradle_cmd: str,
    mas_file: str,
    dry_run: bool,
    base_dir: Path,
) -> tuple[bool, str]:
    cmd = [
        str((base_dir / "gradlew.bat").resolve()),
        "clean",
        "run",
        f"-PgeneratedFolder=convai/600/{sim_dir.name}",
        f"-PmasFile={mas_file}",
    ]

    if dry_run:
        print(f"  [dry] cd {base_dir}  &&  {' '.join(cmd)}")
        return True, f"{sim_dir.name}: dry-run"

    print(f"  [RUN] {sim_dir.name}  ->  gradlew.bat clean run "
          f"-PgeneratedFolder=convai/600/{sim_dir.name} -PmasFile={mas_file}")
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
            # Kill daemons that may still be running after timeout.
            stop_gradle_daemons(base_dir)
            elapsed = time.monotonic() - t0
            return False, f"{sim_dir.name}: TIMEOUT after {elapsed:.1f}s"

        elapsed = time.monotonic() - t0
        success = proc.returncode == 0
        status  = "OK" if success else f"FAILED (rc={proc.returncode})"

        # Stop all Gradle daemons spawned by this run so they don't accumulate.
        stop_gradle_daemons(base_dir)

        return success, f"{sim_dir.name}: {status}  [{elapsed:.1f}s]"

    except FileNotFoundError:
        return False, (
            f"{sim_dir.name}: ERROR – gradlew.bat not found at {base_dir}."
        )


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
    roots = [
        base_dir / "convai" / "600",
        base_dir / "convai" / "600_llm",
    ]

    sim_dirs = []
    for root in roots:
        sim_dirs.extend(discover_sim_folders(root))

    sim_dirs = sorted(set(sim_dirs))  # deduplicate + stable order

    if not sim_dirs:
        print(f"No subfolders found under {roots}.\n"
              "Run generate_sim_folders.py first.")
        return

    print(f"Discovered {len(sim_dirs)} simulation folder(s):\n")
    for d in sim_dirs:
        print(f"  {d.name}")
    print()

    results: list[tuple[bool, str]] = []

    for sim_dir in sim_dirs:
        ok, msg = run_gradle(sim_dir, gradle_cmd, mas_file, dry_run, base_dir)
        results.append((ok, msg))
        icon = "✓" if ok else "✗"
        print(f"  {icon} {msg}")
        if not ok and stop_on_error:
            print("\nStopping on first error (--stop-on-error).")
            break

    # Summary
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