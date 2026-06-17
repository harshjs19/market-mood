#!/usr/bin/env python3
"""
AlphaLens Pipeline Runner
==========================
Orchestrates the full AlphaLens data pipeline end-to-end:

    1. Fetch news articles from configured sources
    2. Persist raw articles into the SQLite database
    3. Run FinBERT sentiment analysis on new headlines
    4. Aggregate per-ticker sentiment scores
    5. Generate actionable BUY / HOLD / SELL signals

Usage:
    python run_pipeline.py

Exit codes:
    0  -- all stages completed successfully
    1  -- one or more stages failed
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Resolve the project root relative to this script so it works regardless
# of the current working directory at invocation time.
PROJECT_ROOT: Path = Path(__file__).resolve().parent

# Python interpreter — use the same interpreter that launched this script
# so virtualenv / venv activation is respected automatically.
PYTHON: str = sys.executable

# Ordered list of pipeline stages.
# Each entry is a (label, relative script path) tuple.
STAGES: list[tuple[str, Path]] = [
    ("Fetching news",             PROJECT_ROOT / "collectors" / "get_news.py"),
    ("Saving news to database",   PROJECT_ROOT / "database"   / "save_news.py"),
    ("Running sentiment analysis", PROJECT_ROOT / "analysis"   / "analyze_news.py"),
    ("Aggregating sentiment",     PROJECT_ROOT / "analysis"   / "aggregate_sentiment.py"),
    ("Generating signals",        PROJECT_ROOT / "analysis"   / "generate_signals.py"),
]

# Visual formatting constants
DIVIDER = "=" * 48
SUBDIV  = "-" * 48


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_stage(label: str, script: Path, index: int, total: int) -> bool:
    """Execute a single pipeline stage and report its outcome.

    Parameters
    ----------
    label:
        Human-readable description printed before execution.
    script:
        Absolute path to the Python script to run.
    index:
        1-based stage number (for progress display).
    total:
        Total number of stages.

    Returns
    -------
    bool
        ``True`` if the stage succeeded, ``False`` otherwise.
    """
    print(f"\n[{index}/{total}] {label}...")
    print(f"       > {script.relative_to(PROJECT_ROOT)}")

    # Guard: make sure the script file actually exists before attempting
    # to run it — gives a clearer error message than a Python traceback.
    if not script.is_file():
        print(f"  FAILED -- script not found: {script}")
        return False

    stage_start = time.perf_counter()

    try:
        result = subprocess.run(
            [PYTHON, str(script)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,  # 10-minute safety timeout per stage
        )
    except subprocess.TimeoutExpired:
        print(f"  FAILED -- stage timed out after 600 seconds")
        return False
    except OSError as exc:
        print(f"  FAILED -- could not launch process: {exc}")
        return False

    elapsed = time.perf_counter() - stage_start

    # Print captured stdout (if any) indented for readability.
    if result.stdout and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            print(f"       {line}")

    if result.returncode == 0:
        print(f"  SUCCESS ({elapsed:.1f}s)")
        return True

    # Stage failed — show stderr to aid debugging.
    print(f"  FAILED (exit code {result.returncode}, {elapsed:.1f}s)")
    if result.stderr and result.stderr.strip():
        print(f"       stderr:")
        for line in result.stderr.strip().splitlines():
            print(f"         {line}")
    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Run the full AlphaLens pipeline and return an exit code."""
    total = len(STAGES)
    passed = 0
    failed_stage: str | None = None

    print(f"\n{DIVIDER}")
    print("  ALPHALENS PIPELINE STARTED")
    print(f"{DIVIDER}")
    print(f"  Stages    : {total}")
    print(f"  Python    : {PYTHON}")
    print(f"  Project   : {PROJECT_ROOT}")

    pipeline_start = time.perf_counter()

    for index, (label, script) in enumerate(STAGES, 1):
        success = _run_stage(label, script, index, total)
        if success:
            passed += 1
        else:
            failed_stage = label
            break  # Stop immediately on first failure

    pipeline_elapsed = time.perf_counter() - pipeline_start

    # --------------- Summary ---------------
    print(f"\n{DIVIDER}")

    if failed_stage is None:
        print("  PIPELINE COMPLETED SUCCESSFULLY")
    else:
        print(f"  PIPELINE FAILED at: {failed_stage}")

    print(f"{SUBDIV}")
    print(f"  Stages passed : {passed}/{total}")
    print(f"  Execution time: {pipeline_elapsed:.1f}s")
    print(f"{DIVIDER}\n")

    return 0 if failed_stage is None else 1


if __name__ == "__main__":
    sys.exit(main())