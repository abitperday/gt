"""Create a telemetry overview image for a recorded GT7 session."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
# Keep Matplotlib's cache inside the project so the command also works in
# restricted environments where the user's home directory is read-only.
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".run" / "matplotlib"))

import matplotlib

# This is a command-line utility; a display server must not be required.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pandas as pd


SESSIONS_DIR = PROJECT_ROOT / ".run" / "storage" / "_data"
REQUIRED_COLUMNS = ("speed", "throttle", "brake", "gear")
PLOTS = (
    ("speed", "Speed (km/h)", "#1f77b4"),
    ("throttle", "Throttle (%)", "#2ca02c"),
    ("brake", "Brake (%)", "#d62728"),
    ("gear", "Gear", "#9467bd"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a four-panel telemetry chart for a GT7 session."
    )
    parser.add_argument(
        "session_id",
        nargs="?",
        help="session directory name (defaults to the most recently modified session)",
    )
    return parser.parse_args()


def find_session(session_id: str | None) -> Path:
    if not SESSIONS_DIR.exists():
        raise ValueError(
            f"No telemetry sessions found: '{SESSIONS_DIR}' does not exist."
        )

    if session_id:
        session_dir = SESSIONS_DIR / session_id
        if not session_dir.is_dir():
            raise ValueError(
                f"Session '{session_id}' was not found in '{SESSIONS_DIR}'."
            )
        return session_dir

    sessions = [path for path in SESSIONS_DIR.iterdir() if path.is_dir()]
    if not sessions:
        raise ValueError(f"No telemetry sessions found in '{SESSIONS_DIR}'.")
    return max(sessions, key=lambda path: path.stat().st_mtime)


def load_laps(session_dir: Path) -> list[tuple[str, pd.DataFrame]]:
    csv_files = sorted(session_dir.glob("lap_*.csv"))
    if not csv_files:
        raise ValueError(
            f"No lap CSV files matching 'lap_*.csv' found in '{session_dir}'."
        )

    laps: list[tuple[str, pd.DataFrame]] = []
    for csv_file in csv_files:
        try:
            lap = pd.read_csv(csv_file)
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
            raise ValueError(f"Could not read '{csv_file}': {error}") from error

        missing = [column for column in REQUIRED_COLUMNS if column not in lap.columns]
        if missing:
            raise ValueError(
                f"'{csv_file}' is missing required column(s): {', '.join(missing)}."
            )
        laps.append((csv_file.stem, lap))
    return laps


def x_values(lap: pd.DataFrame) -> tuple[pd.Series, str]:
    if "dist" in lap.columns:
        distance = pd.to_numeric(lap["dist"], errors="coerce")
        if distance.nunique(dropna=True) > 1:
            return distance, "Distance (m)"
    return pd.Series(range(len(lap)), index=lap.index), "Sample"


def create_graph(session_dir: Path, laps: list[tuple[str, pd.DataFrame]]) -> Path:
    figure, axes = plt.subplots(
        4, 1, figsize=(16, 12), sharex=False, layout="constrained"
    )

    for axis, (column, ylabel, color) in zip(axes, PLOTS, strict=True):
        for lap_name, lap in laps:
            x_axis, x_label = x_values(lap)
            values = pd.to_numeric(lap[column], errors="coerce")
            axis.plot(x_axis, values, label=lap_name, color=color, alpha=0.85)
            axis.set_xlabel(x_label)
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.25)
        if column in {"throttle", "brake"}:
            axis.set_ylim(0, 100)
        if column == "gear":
            axis.yaxis.set_major_locator(MaxNLocator(integer=True))

    if len(laps) > 1:
        axes[0].legend(title="Lap")
    figure.suptitle(f"GT7 telemetry overview — {session_dir.name}", fontsize=16)

    output_dir = PROJECT_ROOT / "images" / session_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "telemetry-overview.png"
    figure.savefig(output_file, dpi=160)
    plt.close(figure)
    return output_file


def main() -> int:
    args = parse_args()
    try:
        session_dir = find_session(args.session_id)
        laps = load_laps(session_dir)
        output_file = create_graph(session_dir, laps)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Generated telemetry overview: {output_file.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
