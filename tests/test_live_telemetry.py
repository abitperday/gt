import struct
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


@pytest.mark.parametrize(
    ("flags", "raw_boost", "has_turbo"),
    [
        (0, 0.0, False),
        ((1 << 3) | (1 << 5) | (1 << 7) | (1 << 15), 1.5, False),
        (1 << 4, 0.5, True),
        (0xFFFF, 2.25, True),
    ],
)
def test_turbo_equipment_flag_and_boost_reach_the_browser(flags, raw_boost, has_turbo):
    packet = bytearray(296)
    struct.pack_into("<H", packet, 0x8E, flags)
    struct.pack_into("<f", packet, 0x50, raw_boost)

    event = TelemetryStat.from_bytes(bytes(packet), None)
    assert event is not None
    assert event.has_turbo is has_turbo

    frame = LiveFrame.from_telemetry(event).model_dump(mode="json")
    assert frame["has_turbo"] is has_turbo
    # One bar equals one unit on a gauge labelled ×100 kPa.
    assert frame["boost"] == pytest.approx(raw_boost - 1)


def test_historical_telemetry_without_turbo_flag_remains_compatible():
    frame = LiveFrame.from_telemetry(telemetry(boost=None))

    assert frame.has_turbo is False
    assert frame.boost is None


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
    assert frame.track_trace == [(0.0, 0.0), (10.0, 0.0), (0.0, 0.0)]
    assert frame.track_tone == "neutral"


def test_hub_completes_the_green_flag_gap_with_the_next_lap_prefix():
    hub = LiveTelemetryHub()
    # The first active packet arrives six metres after the line (green flag).
    hub.publish(telemetry(current_lap=1, lap_distance=6, x=6, y=0, received_at=102.0))
    hub.publish(telemetry(current_lap=1, lap_distance=15, x=15, y=0, received_at=103.0))
    # The next lap supplies the real 0m -> 6m prefix before the map is shown.
    hub.publish(telemetry(current_lap=2, lap_distance=0, x=0, y=0, received_at=104.0))
    hub.publish(telemetry(current_lap=2, lap_distance=6, x=6, y=0, received_at=105.0))

    snapshot = hub.snapshot()
    assert snapshot is not None
    assert snapshot[1].track_ready is True
    assert snapshot[1].track_trace == [(0.0, 0.0), (6.0, 0.0), (15.0, 0.0), (0.0, 0.0)]


def test_parsed_packets_fill_the_missing_start_even_when_first_distance_is_zero(monkeypatch):
    monkeypatch.setattr("src.services.live_telemetry.time.monotonic", lambda: 100.0)
    hub = LiveTelemetryHub()
    tracker = Tracker(db=object(), live_hub=hub)  # type: ignore[arg-type]
    tracker.set_recording_enabled(False)

    def publish_packet(lap, x, y):
        packet = bytearray(296)
        struct.pack_into("<h", packet, 0x74, lap)
        struct.pack_into("<H", packet, 0x8E, 1)
        struct.pack_into("<f", packet, 0x04, x)
        struct.pack_into("<f", packet, 0x0C, -y)
        tracker.process_event(bytes(packet))
        return hub.snapshot()[1]  # type: ignore[index]

    # Parsing begins after the start-line corner, not at the line. The parser
    # still reports zero because lap_distance is accumulated from received data.
    publish_packet(1, 20, 20)
    assert tracker.prev_event is not None and tracker.prev_event.lap_distance == 0
    publish_packet(1, 30, 20)
    publish_packet(1, 40, 0)

    assert publish_packet(2, 0, 0).track_ready is False
    assert publish_packet(2, 0, 10).track_ready is False
    assert publish_packet(2, 10, 20).track_ready is False
    # Even a point close to the original start must not close the missing road
    # while the vehicle is still approaching it.
    assert publish_packet(2, 15, 20).track_ready is False
    completed = publish_packet(2, 20, 20)

    assert completed.track_ready is True
    assert completed.track_trace == [
        (0.0, 0.0), (0.0, 10.0), (10.0, 20.0), (15.0, 20.0),
        (20.0, 20.0), (30.0, 20.0), (40.0, 0.0), (0.0, 0.0),
    ]
    # Completion bypasses snapshot throttling, even when no monotonic time has
    # passed since the lap-transition snapshot.
    assert completed.track_recording_lap == 1
    assert publish_packet(2, 35, 20).track_trace is None
    assert hub.snapshot(include_track=True)[1].track_trace == completed.track_trace  # type: ignore[index]


def test_track_prefix_can_join_a_different_forward_racing_line():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, lap_distance=0, x=20, y=20))
    hub.publish(telemetry(current_lap=1, x=30, y=20))
    hub.publish(telemetry(current_lap=1, x=40, y=0))
    hub.publish(telemetry(current_lap=2, lap_distance=0, x=0, y=0))
    hub.publish(telemetry(current_lap=2, x=15, y=24))
    assert hub.snapshot()[1].track_ready is False  # type: ignore[index]

    hub.publish(telemetry(current_lap=2, x=23, y=24))

    frame = hub.snapshot()[1]  # type: ignore[index]
    assert frame.track_ready is True
    assert frame.track_trace == [(0.0, 0.0), (15.0, 24.0), (23.0, 24.0), (30.0, 20.0), (40.0, 0.0), (0.0, 0.0)]


def test_track_uses_a_complete_following_lap_if_the_partial_trace_never_matches():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, x=100, y=100))
    hub.publish(telemetry(current_lap=1, x=110, y=100))
    following_lap = [(0, 0), (30, 0), (30, 30), (0, 30)]
    for x, y in following_lap:
        hub.publish(telemetry(current_lap=2, x=x, y=y))
        assert hub.snapshot()[1].track_ready is False  # type: ignore[index]

    hub.publish(telemetry(current_lap=3, x=0, y=0))

    frame = hub.snapshot()[1]  # type: ignore[index]
    assert frame.track_ready is True
    assert frame.track_trace == following_lap + [(0, 0)]


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
    assert restored is not None and restored[1].track_trace == [(0.0, 0.0), (10.0, 0.0), (0.0, 0.0)]


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


def test_hub_refreshes_completed_lap_delta_when_a_lap_matches_the_best():
    hub = LiveTelemetryHub()
    hub.publish(telemetry(current_lap=1, lap_distance=0, received_at=100.0))
    hub.publish(telemetry(current_lap=2, lap_distance=0, last_lap=100_000, received_at=200.0))
    hub.publish(telemetry(current_lap=3, lap_distance=0, last_lap=105_000, received_at=300.0))
    assert hub.snapshot()[1].last_lap_delta_ms == 5_000  # type: ignore[index]

    hub.publish(telemetry(current_lap=4, lap_distance=0, last_lap=100_000, received_at=400.0))
    assert hub.snapshot()[1].last_lap_delta_ms == 0  # type: ignore[index]


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


def test_tracker_can_keep_live_telemetry_while_recording_is_disabled(monkeypatch):
    event = telemetry(current_lap=1, in_race=True, total_laps=3)
    hub = LiveTelemetryHub()
    tracker = Tracker(db=object(), live_hub=hub)  # type: ignore[arg-type]
    monkeypatch.setattr(TelemetryStat, "from_bytes", lambda *_args: event)

    assert tracker.set_recording_enabled(False) is False
    tracker.process_event(b"decrypted GT7 packet")

    assert tracker.race_tracker is None
    assert hub.snapshot() is not None
    assert tracker.recording_enabled is False


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
