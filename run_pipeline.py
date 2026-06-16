from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import time


# ----------------------------
# CONFIGURATION
# ----------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_EXECUTABLE = sys.executable


@dataclass(frozen=True)
class PipelineStep:
    """Represents one executable step in the AlphaLens data pipeline."""

    name: str
    script_path: Path


PIPELINE_STEPS = (
    PipelineStep(
        name="Collect financial news",
        script_path=Path("collectors/get_news.py"),
    ),
    PipelineStep(
        name="Save news to SQLite",
        script_path=Path("database/save_news.py"),
    ),
    PipelineStep(
        name="Collect ticker prices",
        script_path=Path("collectors/get_prices.py"),
    ),
    PipelineStep(
        name="Save prices to SQLite",
        script_path=Path("database/save_prices.py"),
    ),
    PipelineStep(
        name="Analyze news sentiment",
        script_path=Path("analysis/analyze_news.py"),
    ),
    PipelineStep(
        name="Generate trading signals",
        script_path=Path("analysis/generate_signals.py"),
    ),
)


# ----------------------------
# CONSOLE HELPERS
# ----------------------------

def format_duration(seconds: float) -> str:
    """Format elapsed seconds as a compact runtime string."""

    minutes, remaining_seconds = divmod(seconds, 60)

    if minutes >= 1:
        return f"{int(minutes)}m {remaining_seconds:.2f}s"

    return f"{remaining_seconds:.2f}s"


def print_header() -> None:
    """Print a professional run header before starting subprocesses."""

    print("=" * 72)
    print("AlphaLens Data Pipeline")
    print("=" * 72)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Python       : {PYTHON_EXECUTABLE}")
    print(f"Steps        : {len(PIPELINE_STEPS)}")
    print("-" * 72)


def print_footer(total_runtime: float) -> None:
    """Print the success footer after all steps complete."""

    print("-" * 72)
    print("Pipeline completed successfully")
    print(f"Total runtime: {format_duration(total_runtime)}")
    print("=" * 72)


def print_failure(step: PipelineStep, return_code: int, total_runtime: float) -> None:
    """Print a fail-fast summary when a subprocess exits unsuccessfully."""

    print("-" * 72)
    print("Pipeline failed")
    print(f"Failed step  : {step.name}")
    print(f"Exit code    : {return_code}")
    print(f"Total runtime: {format_duration(total_runtime)}")
    print("=" * 72)


# ----------------------------
# PIPELINE EXECUTION
# ----------------------------

def validate_step_script(step: PipelineStep) -> Path:
    """Ensure the step script exists before attempting to run it."""

    absolute_script_path = PROJECT_ROOT / step.script_path

    if not absolute_script_path.exists():
        raise FileNotFoundError(
            f"Pipeline step script not found: {absolute_script_path}"
        )

    if not absolute_script_path.is_file():
        raise FileNotFoundError(
            f"Pipeline step path is not a file: {absolute_script_path}"
        )

    return absolute_script_path


def run_step(step_number: int, total_steps: int, step: PipelineStep) -> int:
    """Run a single pipeline step as a subprocess and return its exit code."""

    absolute_script_path = validate_step_script(step)

    print(f"\n[{step_number}/{total_steps}] {step.name}")
    print(f"Script: {step.script_path}")
    print("-" * 72)

    step_start = time.perf_counter()

    completed_process = subprocess.run(
        [
            PYTHON_EXECUTABLE,
            str(absolute_script_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )

    step_runtime = time.perf_counter() - step_start

    if completed_process.returncode == 0:
        print(f"Status: completed in {format_duration(step_runtime)}")
    else:
        print(f"Status: failed in {format_duration(step_runtime)}")

    return completed_process.returncode


def run_pipeline() -> int:
    """Run the full AlphaLens pipeline in the required order."""

    pipeline_start = time.perf_counter()
    print_header()

    try:
        for step_number, step in enumerate(PIPELINE_STEPS, start=1):
            return_code = run_step(
                step_number=step_number,
                total_steps=len(PIPELINE_STEPS),
                step=step,
            )

            if return_code != 0:
                total_runtime = time.perf_counter() - pipeline_start
                print_failure(
                    step=step,
                    return_code=return_code,
                    total_runtime=total_runtime,
                )
                return return_code

    except KeyboardInterrupt:
        total_runtime = time.perf_counter() - pipeline_start
        print("-" * 72)
        print("Pipeline interrupted by user")
        print(f"Total runtime: {format_duration(total_runtime)}")
        print("=" * 72)
        return 130

    except Exception as exc:
        total_runtime = time.perf_counter() - pipeline_start
        print("-" * 72)
        print("Pipeline failed before completion")
        print(f"Error        : {exc}")
        print(f"Total runtime: {format_duration(total_runtime)}")
        print("=" * 72)
        return 1

    total_runtime = time.perf_counter() - pipeline_start
    print_footer(total_runtime)

    return 0


if __name__ == "__main__":
    raise SystemExit(run_pipeline())