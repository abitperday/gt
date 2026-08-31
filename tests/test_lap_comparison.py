import pandas as pd
import pytest

from src.services.lap_comparison import ComparisonError, compare_laps, interpolate_elapsed, prepare_lap


def test_interpolates_elapsed_time_using_normalized_distance():
    lap = pd.DataFrame({"dist": [10, 30, 70, 110]})
    prepared = prepare_lap(lap, 12_000)

    assert interpolate_elapsed(prepared.samples, 0.2) == 4_000
    assert interpolate_elapsed(prepared.samples, 0.5) == 7_000


def test_delta_is_a_minus_b_and_matches_finish_time():
    lap_a = pd.DataFrame({"dist": [0, 50, 100]})
    lap_b = pd.DataFrame({"dist": [0, 50, 100]})

    comparison = compare_laps(lap_a, 10_000, lap_b, 8_000)

    midpoint = comparison["points"][100]
    assert midpoint["progress"] == 0.5
    assert midpoint["delta_ms"] == 1_000
    assert comparison["points"][-1]["delta_ms"] == 2_000
    assert comparison["final_delta_ms"] == 2_000


def test_rejects_discontinuous_distance_data():
    lap = pd.DataFrame({"dist": [0, 1, 2, 500]})

    with pytest.raises(ComparisonError, match="discontinuous"):
        prepare_lap(lap, 10_000)
