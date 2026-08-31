"""Distance-based, non-diagnostic lap comparison utilities."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from math import isfinite
from typing import Iterable

import pandas as pd


AXIS_STEPS = 200
MIN_SAMPLES = 3
MAX_COVERAGE_DIFFERENCE = 0.05
MAX_DISTANCE_GAP_MULTIPLIER = 25


class ComparisonError(ValueError):
    """Raised when telemetry cannot support a trustworthy comparison."""


@dataclass(frozen=True)
class ProgressSample:
    progress: float
    elapsed_ms: float


@dataclass(frozen=True)
class PreparedLap:
    samples: list[ProgressSample]
    distance_span: float
    lap_time_ms: int


def _finite_distances(values: Iterable[object]) -> list[float | None]:
    distances: list[float | None] = []
    for value in values:
        try:
            distance = float(value)
        except (TypeError, ValueError):
            distances.append(None)
            continue
        distances.append(distance if isfinite(distance) else None)
    return distances


def prepare_lap(lap: pd.DataFrame, lap_time_ms: int) -> PreparedLap:
    """Normalize a lap's sequential distance samples and reconstruct elapsed time.

    CSV telemetry does not store a per-packet timestamp. The recorded lap duration is
    distributed across its sequential samples, which is valid only when distance is
    continuous and monotonically increasing.
    """
    if lap_time_ms <= 0:
        raise ComparisonError("The lap has no valid recorded duration.")
    if "dist" not in lap.columns:
        raise ComparisonError("The lap telemetry does not contain a distance column.")

    raw_distances = _finite_distances(lap["dist"])
    valid = [(index, distance) for index, distance in enumerate(raw_distances) if distance is not None]
    if len(valid) < MIN_SAMPLES:
        raise ComparisonError("The lap has too few valid distance samples.")

    distances = [distance for _, distance in valid]
    changes = [next_distance - distance for distance, next_distance in zip(distances, distances[1:])]
    if any(change < 0 for change in changes):
        raise ComparisonError("The lap distance moves backwards, so physical progress is inconsistent.")

    positive_changes = [change for change in changes if change > 0]
    if len(positive_changes) < MIN_SAMPLES - 1:
        raise ComparisonError("The lap has insufficient distance progress.")

    median_change = sorted(positive_changes)[len(positive_changes) // 2]
    if max(positive_changes) > median_change * MAX_DISTANCE_GAP_MULTIPLIER:
        raise ComparisonError("The lap has a discontinuous distance gap, so it cannot be aligned reliably.")

    start_distance = distances[0]
    end_distance = distances[-1]
    distance_span = end_distance - start_distance
    if distance_span <= 0:
        raise ComparisonError("The lap has no usable distance coverage.")

    total_samples = len(raw_distances) - 1
    samples: list[ProgressSample] = []
    for index, distance in valid:
        progress = (distance - start_distance) / distance_span
        elapsed_ms = lap_time_ms * index / total_samples
        if samples and progress == samples[-1].progress:
            samples[-1] = ProgressSample(progress, elapsed_ms)
        else:
            samples.append(ProgressSample(progress, elapsed_ms))

    if len(samples) < MIN_SAMPLES:
        raise ComparisonError("The lap has too few unique distance samples.")
    return PreparedLap(samples=samples, distance_span=distance_span, lap_time_ms=lap_time_ms)


def interpolate_elapsed(samples: list[ProgressSample], progress: float) -> float:
    """Linearly interpolate elapsed time at a normalized physical progress value."""
    progress_values = [sample.progress for sample in samples]
    right_index = bisect_left(progress_values, progress)
    if right_index == 0:
        return samples[0].elapsed_ms
    if right_index == len(samples):
        return samples[-1].elapsed_ms

    right = samples[right_index]
    left = samples[right_index - 1]
    if right.progress == left.progress:
        return right.elapsed_ms
    fraction = (progress - left.progress) / (right.progress - left.progress)
    return left.elapsed_ms + fraction * (right.elapsed_ms - left.elapsed_ms)


def compare_laps(lap_a: pd.DataFrame, time_a_ms: int, lap_b: pd.DataFrame, time_b_ms: int) -> dict:
    """Return elapsed-time delta points where positive means lap A is behind lap B."""
    prepared_a = prepare_lap(lap_a, time_a_ms)
    prepared_b = prepare_lap(lap_b, time_b_ms)
    larger_span = max(prepared_a.distance_span, prepared_b.distance_span)
    coverage_difference = abs(prepared_a.distance_span - prepared_b.distance_span) / larger_span
    if coverage_difference > MAX_COVERAGE_DIFFERENCE:
        raise ComparisonError(
            "The laps cover materially different distances, so they cannot be aligned reliably."
        )

    points = []
    for step in range(AXIS_STEPS + 1):
        progress = step / AXIS_STEPS
        elapsed_a_ms = interpolate_elapsed(prepared_a.samples, progress)
        elapsed_b_ms = interpolate_elapsed(prepared_b.samples, progress)
        points.append(
            {
                "progress": progress,
                "elapsed_a_ms": elapsed_a_ms,
                "elapsed_b_ms": elapsed_b_ms,
                "delta_ms": elapsed_a_ms - elapsed_b_ms,
            }
        )

    return {
        "points": points,
        "final_delta_ms": time_a_ms - time_b_ms,
        "sign_convention": "A minus B; positive means Lap A is behind Lap B.",
    }
