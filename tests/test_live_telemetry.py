import time

import pytest

from src.schema.telemetry import TelemetryStat, tyre_slip_ratio
from src.services.live_telemetry import LiveFrame, LiveTelemetryHub
from src.services.tracker import Tracker


def telemetry(**overrides) -> TelemetryStat:
    values = {
        "package_id": 42,
        "current_lap": 3,
        "current_gear": 4,
        "suggested_gear": 3,
        "speed": 181,
        "total_laps": 5,
        "current_position": 2,
        "total_racers": 12,
        "rpm": 7200.5,
        "throttle_rate": 83,
        "brake_rate": 0,
        "x": 0,
        "y": 0,
        "z": 0,
        "time_on_track": 0,
        "lap_distance": 1234.5,
        "best_lap": 81234,
        "last_lap": 82000,
        "in_race": True,
        "car_id": 987,
        "received_at": time.time(),
        "fuel_current": 25.0,
        "fuel_capacity": 50.0,
        "tyre_slip_rl": 0.2,
    }
    values.update(overrides)
    return TelemetryStat.model_validate(values)


def test_live_frame_serializes_browser_facing_units_and_optional_values():
    frame = LiveFrame.from_telemetry(telemetry(x=123.5, y=-88.25, z=7.5))

    assert frame.packet_id == 42
    assert frame.speed_kmh == 181
    assert frame.fuel_l == 25.0
    assert frame.best_lap_ms == 81234
    assert frame.tyre_slip_rl == 0.2
    assert frame.position_x == 123.5
    assert frame.position_y == -88.25
    assert frame.elevation_m == 7.5


def test_hub_retains_a_complete_planar_trace_for_new_dashboard_connections():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, lap_distance=0, x=0, y=0, received_at=100.0))
    hub.publish(telemetry(current_lap=1, lap_distance=10, x=10, y=0, received_at=101.0))
    hub.publish(telemetry(current_lap=2, lap_distance=0, x=0, y=0, received_at=102.0))

    snapshot = hub.snapshot()
    assert snapshot is not None
    frame = snapshot[1]
    assert frame.session_id == 1
    assert frame.track_ready is True
    assert frame.track_trace == [(0.0, 0.0), (10.0, 0.0)]
    assert frame.track_tone == "neutral"


def test_hub_colours_the_persistent_trace_only_after_a_valid_lap_comparison():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, lap_distance=0, x=0, y=0, received_at=100.0))
    hub.publish(telemetry(current_lap=1, lap_distance=10, x=10, y=0, received_at=101.0))
    hub.publish(telemetry(current_lap=2, lap_distance=0, x=0, y=0, last_lap=100_000, received_at=102.0))
    assert hub.snapshot()[1].track_tone == "neutral"  # type: ignore[index]

    hub.publish(telemetry(current_lap=3, lap_distance=0, x=0, y=0, last_lap=101_000, received_at=103.0))
    assert hub.snapshot()[1].track_tone == "slow"  # type: ignore[index]

    hub.publish(telemetry(current_lap=4, lap_distance=0, x=0, y=0, last_lap=99_000, received_at=104.0))
    assert hub.snapshot()[1].track_tone == "fast"  # type: ignore[index]


def test_hub_can_restore_the_server_held_trace_without_resending_it_per_frame():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, lap_distance=0, x=0, y=0, received_at=100.0))
    hub.publish(telemetry(current_lap=1, lap_distance=10, x=10, y=0, received_at=101.0))
    hub.publish(telemetry(current_lap=2, lap_distance=0, x=0, y=0, received_at=102.0))
    hub.publish(telemetry(current_lap=2, lap_distance=20, x=0, y=20, received_at=103.0))

    latest = hub.snapshot()
    restored = hub.snapshot(include_track=True)
    assert latest is not None and latest[1].track_trace is None
    assert restored is not None and restored[1].track_trace == [(0.0, 0.0), (10.0, 0.0)]


def test_hub_is_latest_wins_without_a_packet_backlog():
    hub = LiveTelemetryHub()
    first_sequence = hub.publish(telemetry(package_id=1))
    second_sequence = hub.publish(telemetry(package_id=2))

    sequence, frame = hub.wait_for_update(first_sequence, timeout=0.01) or (0, None)
    assert second_sequence == first_sequence + 1
    assert sequence == second_sequence
    assert frame is not None
    assert frame.packet_id == 2


def test_hub_aligns_live_delta_to_reference_lap_distance():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, lap_distance=0, received_at=100.0))
    hub.publish(telemetry(current_lap=1, lap_distance=100, received_at=105.0))
    hub.publish(telemetry(current_lap=2, lap_distance=0, received_at=110.0))
    hub.publish(telemetry(current_lap=2, lap_distance=50, received_at=113.0))

    snapshot = hub.snapshot()
    assert snapshot is not None
    assert snapshot[1].delta_to_reference_ms == pytest.approx(500.0)


def test_hub_does_not_compare_first_lap_with_stale_game_best():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, lap_distance=0, received_at=100.0, best_lap=70000))
    hub.publish(telemetry(current_lap=2, lap_distance=0, received_at=110.0, last_lap=156000, best_lap=70000))
    snapshot = hub.snapshot()
    assert snapshot is not None
    assert snapshot[1].last_lap_delta_ms is None


def test_hub_clears_lap_delta_when_session_restarts():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, lap_distance=0, received_at=100.0))
    hub.publish(telemetry(current_lap=2, lap_distance=0, received_at=110.0, last_lap=80000))
    hub.publish(telemetry(current_lap=0, lap_distance=0, received_at=120.0, last_lap=0))
    snapshot = hub.snapshot()
    assert snapshot is not None
    assert snapshot[1].last_lap_delta_ms is None


def test_tyre_slip_is_numeric_and_suppressed_near_standstill():
    assert tyre_slip_ratio(110, 100) == pytest.approx(0.1)
    assert tyre_slip_ratio(4, 0.5) is None
    assert tyre_slip_ratio(float("nan"), 100) is None


def test_tracker_publishes_a_parsed_packet_before_a_race_starts(monkeypatch):
    event = telemetry(current_lap=0, in_race=False)
    hub = LiveTelemetryHub()
    tracker = Tracker(db=object(), live_hub=hub)  # type: ignore[arg-type]
    monkeypatch.setattr(TelemetryStat, "from_bytes", lambda *_args: event)

    tracker.process_event(b"decrypted GT7 packet")

    snapshot = hub.snapshot()
    assert snapshot is not None
    assert snapshot[1].packet_id == event.package_id


def test_terminal_race_packet_without_captured_laps_does_not_crash_or_restart():
    tracker = Tracker(db=object())  # type: ignore[arg-type]
    before_race = telemetry(current_lap=0, total_laps=1)
    terminal_packet = telemetry(current_lap=2, total_laps=1, last_lap=0)

    tracker._process_parsed_event(before_race)
    tracker._process_parsed_event(terminal_packet)

    assert tracker.race_tracker is None
    assert tracker.prev_event is terminal_packet

    tracker._process_parsed_event(terminal_packet)
    assert tracker.race_tracker is None
